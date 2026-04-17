"""ShopBot Agent 配置 - Single Agent + Tools 架構"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import Literal, Optional, Dict, List

from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage, RemoveMessage, trim_messages
from langchain_core.callbacks import BaseCallbackHandler
from langchain_aws import ChatBedrockConverse
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# 導入工具、State 和存儲
from app.tools import ALL_SHOPBOT_TOOLS
from app.models.state import ShopBotState
from app.models.persistence import create_checkpointer, FileStore

# 載入環境變數
load_dotenv()

# ============================================
# LLM 日志配置
# ============================================

# 创建 logs 目录
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 配置 LLM 日志记录器
llm_logger = logging.getLogger("shopbot.llm")
llm_logger.setLevel(logging.DEBUG)

# 文件处理器（每天一个日志文件）
log_file = LOGS_DIR / f"llm_{datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

# 日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
llm_logger.addHandler(file_handler)

print(f"📝 [Init] LLM 日志将保存到: {log_file}")

# Token 計數器
try:
    import tiktoken
    TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")  # Claude 使用的編碼
    HAS_TIKTOKEN = True
except ImportError:
    TOKEN_ENCODER = None
    HAS_TIKTOKEN = False
    print("⚠️  tiktoken 未安裝，將使用簡單字符計數（建議: pip install tiktoken）")


# ============================================
# LangFuse 集成（可觀測性）
# ============================================

# 全局 LangFuse 回調
_langfuse_handler = None

def init_langfuse() -> Optional[BaseCallbackHandler]:
    """
    初始化 LangFuse 觀測

    從環境變數讀取配置，如果配置完整則啟用 LangFuse。

    Returns:
        LangFuse CallbackHandler 或 None
    """
    global _langfuse_handler

    # 如果已初始化，直接返回
    if _langfuse_handler is not None:
        return _langfuse_handler

    # 檢查是否啟用
    enable_langfuse = os.getenv("ENABLE_LANGFUSE", "false").lower() == "true"

    if not enable_langfuse:
        print("ℹ️  LangFuse 觀測未啟用（設置 ENABLE_LANGFUSE=true 啟用）")
        return None

    try:
        from langfuse.langchain import CallbackHandler

        # 讀取配置
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            print("⚠️  LangFuse 配置不完整，觀測未啟用")
            print("   需要設置: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY")
            return None

        # 創建 CallbackHandler（自動從環境變數讀取配置）
        # 需要確保環境變數已設置：LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
        _langfuse_handler = CallbackHandler()

        print(f"✅ LangFuse 觀測已啟用: {host}")
        return _langfuse_handler

    except ImportError:
        print("⚠️  langfuse 未安裝，觀測未啟用（運行: pip install langfuse）")
        return None
    except Exception as e:
        print(f"⚠️  LangFuse 初始化失敗: {e}")
        return None


def get_langfuse_callbacks() -> List[BaseCallbackHandler]:
    """
    獲取 LangFuse callbacks 列表

    Returns:
        包含 LangFuse handler 的列表，如果未啟用則返回空列表
    """
    handler = init_langfuse()
    return [handler] if handler else []


# ============================================
# User Profile Management
# ============================================

def load_user_profile(user_id: str) -> Dict[str, str]:
    """
    載入用戶畫像

    從 data/user_profiles/{user_id}.json 讀取用戶畫像。
    如果不存在，返回空畫像。

    Args:
        user_id: 用戶 ID

    Returns:
        用戶畫像字典，包含 5 個字段：
        - explicit_preferences: 用戶明說的偏好
        - inferred_preferences: 從行為推斷的偏好
        - stylistic_notes: 風格和溝通方式
        - successful_patterns: 成功經驗
        - things_to_avoid: 失敗經驗
    """
    profile_path = Path(__file__).parent.parent / "data" / "user_profiles" / f"{user_id}.json"

    # 如果畫像不存在，返回空畫像
    if not profile_path.exists():
        return {
            "user_id": user_id,
            "updated_at": datetime.now().isoformat(),
            "explicit_preferences": "",
            "inferred_preferences": "",
            "stylistic_notes": "",
            "successful_patterns": "",
            "things_to_avoid": ""
        }

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
            return profile
    except Exception as e:
        print(f"⚠️  載入用戶畫像失敗 ({user_id}): {e}")
        # 返回空畫像
        return {
            "user_id": user_id,
            "updated_at": datetime.now().isoformat(),
            "explicit_preferences": "",
            "inferred_preferences": "",
            "stylistic_notes": "",
            "successful_patterns": "",
            "things_to_avoid": ""
        }


# ============================================
# System Prompt Builder
# ============================================

def build_system_prompt(state: dict) -> str:
    """
    構建動態 System Prompt

    根據當前狀態注入上下文信息
    """
    user_id = state.get("user_id", "user_001")
    summary = state.get("summary", "")

    # 如果有摘要，注入到 prompt 中
    summary_section = ""
    if summary:
        summary_section = f"\n- 對話摘要: {summary}\n"

    return f"""你是智能購物助手 ShopBot。

# 當前上下文
- 用戶 ID: {user_id}

# 你的能力
- 訪問 15 個工具來幫助用戶購物
- 循環調用工具直到完成任務
- 自主分析數據並做決策
- Context 自動管理（無需擔心 token 限制）

# 工具使用指南

## 1. 商品搜索和對比
- **搜索商品**: 使用 search_products，只支持關鍵詞搜索
- **獲取詳情**: 單個商品用 get_product_details，多個商品用 get_products_batch
- **商品對比**:
  * 使用 get_products_batch 一次獲取多個商品
  * 自己分析價格、評分、功能差異
  * 自己給出推薦理由（不要依賴工具）

## 2. 購物車管理
- **添加商品**: add_to_cart(user_id, product_id, quantity)
- **查看購物車**: get_cart(user_id)
- **移除商品**: remove_from_cart(user_id, product_id)
- **結賬**: checkout(user_id)

## 3. 購買歷史查詢
- 使用 get_purchase_history，支持分頁和過濾
- **循環查詢**策略（對於"我常買的XX"）:
  * 第一次: limit=10，如果沒找到 →
  * 第二次: limit=50，如果還沒找到 →
  * 第三次: limit=100
- 使用返回的 aggregated 字段快速查看統計信息
- ⚠️ 工具調用有限制（最多 3 次）

## 4. 願望清單
- get_wishlist(user_id)
- add_to_wishlist(user_id, product_id)
- remove_from_wishlist(user_id, product_id)

## 5. 用戶偏好
- get_user_preferences(user_id)

## 6. 價格追蹤
- get_price_history(product_id, days)
- set_price_alert(user_id, product_id, target_price)

## 7. 商品評論
- get_product_reviews(product_id, limit, offset)

# 重要原則

1. **理解商品查看消息**
   - 當消息以 "查看商品：XXX（ID: prod_xxx）" 開頭時：
     * 用戶正在查看該商品
     * 後續內容（空行後）是用戶針對這個商品的提問或操作
   - 例如：
     ```
     查看商品：Nike Air Force 1（prod_001）

     這雙鞋適合跑步嗎？
     ```
     → 理解為：用戶在看 Nike Air Force 1（product_id: prod_001），並詢問是否適合跑步

   - **如何處理**：
     * 如果需要商品詳情，使用 get_product_details("prod_001")
     * 如果用戶說"加購"、"買"、"加入購物車"，product_id 就是 prod_001
     * 商品名稱和 ID 都已提供，優先使用 ID

   - **引用歷史商品**：
     * 用戶說"這個"、"它"時，指最近一次查看的商品
     * 用戶說"剛才那個"、"前一個"時，從對話歷史找前一次查看的商品
     * 如果不確定，禮貌詢問用戶

2. **循環推理**
   - 不要一次性查詢太多數據
   - 先查詢少量，根據結果決定是否需要更多
   - 例如：先 search_products(limit=5)，如果不夠再增加

3. **自主分析**
   - 工具只提供數據，分析和判斷由你完成
   - 商品對比：自己分析價格、評分、功能差異
   - 購買推薦：基於用戶歷史和偏好做推薦

4. **任務規劃**（複雜任務時）
   - 對於多步驟任務（如"幫我籌備生日派對"），使用 write_todos 規劃步驟
   - 逐步完成並標記狀態

5. **用戶體驗**
   - 簡潔友好的回覆
   - 主動提供有用信息
   - 出錯時給出清晰的解釋

# 之前會話
你之前已經和用戶完成了這些對話內容
{summary_section}

# 當前會話
用戶 {user_id} 正在與你對話。保持專業、友好、高效。
"""


# ============================================
# Context Management (Middleware)
# ============================================

def count_tokens(messages: list) -> int:
    """
    計算消息列表的 token 總數

    Args:
        messages: 消息列表

    Returns:
        int: token 總數
    """
    if not messages:
        return 0

    total_tokens = 0

    for msg in messages:
        try:
            # 提取消息內容
            content = ""
            if hasattr(msg, "content"):
                if isinstance(msg.content, str):
                    content = msg.content
                elif isinstance(msg.content, list):
                    # 處理多模態消息（如工具調用）
                    for item in msg.content:
                        if isinstance(item, dict) and "text" in item:
                            content += item["text"]
                        elif isinstance(item, str):
                            content += item

            # 添加工具調用的 token
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    content += str(tool_call)

            # 計算 token
            if HAS_TIKTOKEN and content:
                total_tokens += len(TOKEN_ENCODER.encode(content))
            else:
                # 回退到簡單估算：4 字符 ≈ 1 token
                total_tokens += len(content) // 4

        except Exception as e:
            # 靜默失敗，繼續計數
            pass

    return total_tokens


def compress_messages(messages: list) -> list:
    """
    Context 自動壓縮 Middleware

    功能：
    - 自動裁剪超長對話歷史
    - 保留最近的消息和工具調用
    - 支持 Prompt Caching（Claude 特性）

    Args:
        messages: 原始消息列表

    Returns:
        壓縮後的消息列表
    """
    # 如果消息數量少於閾值，直接返回
    MAX_MESSAGES = 20  # 保留最近 20 條消息

    if len(messages) <= MAX_MESSAGES:
        return messages

    # 使用 trim_messages 智能裁剪
    # 策略：保留最近的消息，同時確保工具調用-結果配對完整
    trimmed = trim_messages(
        messages,
        max_tokens=4000,  # 限制 token 數（約 20 輪對話）
        strategy="last",   # 保留最後的消息
        token_counter=len, # 簡單計數器（實際可用 tiktoken）
        include_system=True,  # 保留 System Message
        allow_partial=False,  # 不允許部分工具調用（確保完整性）
    )

    return trimmed


# ============================================
# Graph Nodes
# ============================================

def agent_node(state: ShopBotState) -> dict:
    """
    Agent 節點 - 調用 LLM 生成響應或工具調用

    集成功能：
    - 用戶畫像自動載入（多 cache block 策略）
    - Context 自動壓縮（Middleware）
    - 動態 System Prompt 注入
    - 商品上下文從消息內容理解（不依賴 State 字段）
    - ReAct 推理循環

    Args:
        state: 當前狀態

    Returns:
        更新後的狀態
    """
    print("\n" + "="*80)
    print("🤖 [AGENT NODE] 開始執行")
    print("="*80)

    # 創建 LLM（每次調用時創建，避免單例問題）
    model = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        temperature=0.7,
    )

    # 綁定工具
    model_with_tools = model.bind_tools(ALL_SHOPBOT_TOOLS)
    print(f"📦 [Agent] 已綁定 {len(ALL_SHOPBOT_TOOLS)} 個工具")

    # 1. 載入用戶畫像
    user_id = state.get("user_id", "Unknown")
    session_id = state.get("session_id", "Unknown")
    print(f"👤 [Agent] User ID: {user_id}")
    print(f"🔗 [Agent] Session ID: {session_id}")

    profile = load_user_profile(user_id)
    has_profile = any([
        profile.get("explicit_preferences"),
        profile.get("inferred_preferences"),
        profile.get("stylistic_notes"),
        profile.get("successful_patterns"),
        profile.get("things_to_avoid")
    ])
    print(f"📋 [Agent] 用戶畫像: {'已載入' if has_profile else '空白'}")

    # 2. Context 壓縮（Middleware）
    original_msg_count = len(state["messages"])
    compressed_messages = compress_messages(state["messages"])
    compressed_msg_count = len(compressed_messages)
    print(f"🗜️  [Agent] 消息壓縮: {original_msg_count} → {compressed_msg_count} 條")

    # 打印最近 3 條消息（用於 debug）
    print(f"📝 [Agent] 最近消息:")
    for i, msg in enumerate(compressed_messages[-3:], 1):
        msg_type = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")
        content_preview = content[:80] if isinstance(content, str) else str(content)[:80]
        print(f"   [{i}] {msg_type}: {content_preview}...")

    # 3. 構建多 cache block 消息列表（利用 Prompt Caching）
    print(f"🏗️  [Agent] 構建消息列表（Prompt Caching 策略）...")
    messages = [
        # Block 1: System Prompt（永不變，100% 緩存）
        SystemMessage(
            content=build_system_prompt(state),
            additional_kwargs={"cache_control": {"type": "ephemeral"}}
        ),
    ]

    # Block 2: 用戶畫像（很少變，95% 緩存）
    # 只有當畫像非空時才注入
    if any([
        profile.get("explicit_preferences"),
        profile.get("inferred_preferences"),
        profile.get("stylistic_notes"),
        profile.get("successful_patterns"),
        profile.get("things_to_avoid")
    ]):
        profile_content = f"""# 關於我

## 我明確說過的偏好
{profile.get('explicit_preferences', '暫無')}

## 你觀察到的我的偏好
{profile.get('inferred_preferences', '暫無')}

## 我的風格
{profile.get('stylistic_notes', '暫無')}

## 過往經驗
### 什麼對我有效
{profile.get('successful_patterns', '暫無')}

### 請避免
{profile.get('things_to_avoid', '暫無')}
"""
        messages.append(
            HumanMessage(
                content=profile_content,
                additional_kwargs={"cache_control": {"type": "ephemeral"}}
            )
        )

        # Block 3: 確認（永不變，100% 緩存）
        messages.append(
            AIMessage(
                content="明白，我會根據您的偏好推薦。",
                additional_kwargs={"cache_control": {"type": "ephemeral"}}
            )
        )

    # Block 4: 當前對話（每次都變，不緩存）
    messages.extend(compressed_messages)
    print(f"📨 [Agent] 最終消息數: {len(messages)} 條 (System + Profile + 對話)")

    # ============================================
    # 记录 LLM 输入到日志文件
    # ============================================
    llm_logger.info("="*80)
    llm_logger.info(f"🔵 [LLM INPUT] Session: {session_id}, User: {user_id}")
    llm_logger.info("="*80)

    for i, msg in enumerate(messages, 1):
        msg_type = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")

        # 记录消息类型和内容
        if isinstance(content, str):
            llm_logger.info(f"Message [{i}] - Type: {msg_type}")
            llm_logger.info(f"Content:\n{content}")
        elif isinstance(content, list):
            llm_logger.info(f"Message [{i}] - Type: {msg_type} (multimodal)")
            llm_logger.info(f"Content: {json.dumps(content, ensure_ascii=False, indent=2)}")

        # 如果是 AI 消息且有 tool_calls，记录
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            llm_logger.info(f"Tool Calls: {json.dumps(msg.tool_calls, ensure_ascii=False, indent=2)}")

        llm_logger.info("-" * 40)

    llm_logger.info(f"Total Messages: {len(messages)}")
    llm_logger.info("="*80)

    # 4. 調用 LLM（帶 LangFuse 觀測）
    print(f"🚀 [Agent] 調用 Claude Sonnet 4.5...")
    callbacks = get_langfuse_callbacks()
    config = {"callbacks": callbacks} if callbacks else {}
    response = model_with_tools.invoke(messages, config=config)

    # ============================================
    # 记录 LLM 输出到日志文件
    # ============================================
    llm_logger.info("="*80)
    llm_logger.info(f"🟢 [LLM OUTPUT] Session: {session_id}, User: {user_id}")
    llm_logger.info("="*80)

    # 记录响应类型
    response_type = getattr(response, "type", "unknown")
    llm_logger.info(f"Response Type: {response_type}")

    # 记录文本内容
    if hasattr(response, "content"):
        if isinstance(response.content, str):
            llm_logger.info(f"Content:\n{response.content}")
        elif isinstance(response.content, list):
            llm_logger.info(f"Content (multimodal):\n{json.dumps(response.content, ensure_ascii=False, indent=2)}")

    # 记录工具调用
    if hasattr(response, "tool_calls") and response.tool_calls:
        llm_logger.info(f"Tool Calls ({len(response.tool_calls)}):")
        for i, tc in enumerate(response.tool_calls, 1):
            llm_logger.info(f"  [{i}] {tc['name']}")
            llm_logger.info(f"      Args: {json.dumps(tc.get('args', {}), ensure_ascii=False, indent=6)}")

    # 记录其他元数据
    if hasattr(response, "response_metadata"):
        llm_logger.info(f"Response Metadata: {json.dumps(response.response_metadata, ensure_ascii=False, indent=2)}")

    llm_logger.info("="*80)
    llm_logger.info("")  # 空行分隔

    # 分析響應
    has_tool_calls = hasattr(response, "tool_calls") and response.tool_calls
    if has_tool_calls:
        print(f"🔧 [Agent] LLM 返回工具調用:")
        for i, tc in enumerate(response.tool_calls, 1):
            print(f"   [{i}] {tc['name']}({list(tc.get('args', {}).keys())})")
    else:
        content_preview = response.content[:100] if hasattr(response, "content") else ""
        print(f"💬 [Agent] LLM 返回文本響應: {content_preview}...")

    # 5. 更新時間戳和狀態
    print(f"📝 [Agent] 準備更新 State...")
    updates = {
        "messages": [response],
        "last_message_time": datetime.now().isoformat(),
        "profile_update_status": "pending",  # 每次新消息後標記為待更新
    }

    print(f"✅ [Agent] State 更新:")
    print(f"   - messages: +1 條")
    print(f"   - last_message_time: {updates['last_message_time']}")
    print("="*80)
    print("🤖 [AGENT NODE] 執行完成\n")

    return updates


def context_compressor(state: ShopBotState) -> dict:
    """
    主動 Context 壓縮器 - 當 token 接近上限時觸發

    功能：
    - 監控 context token 數量（閾值：800K tokens）
    - 生成對話摘要，保留關鍵信息
    - 刪除舊消息，只保留最近 10 條 + 摘要
    - 確保 Agent 長時間運行的穩健性

    Args:
        state: 當前狀態

    Returns:
        更新後的狀態（包含新摘要和刪除消息的指令）
    """
    print("\n" + "="*80)
    print("🗜️  [CONTEXT COMPRESSOR] 開始執行（Token 超過閾值）")
    print("="*80)

    messages = state["messages"]
    current_summary = state.get("summary", "")

    # 計算當前 token 數
    total_tokens = count_tokens(messages)
    print(f"📊 [Compressor] 當前 token 數: {total_tokens:,} / 800,000")
    print(f"📝 [Compressor] 當前消息數: {len(messages)} 條")
    print(f"📋 [Compressor] 已有摘要: {'是' if current_summary else '否'}")

    # 創建 LLM 用於生成摘要
    model = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        temperature=0.3,
    )

    # 構建摘要提示
    summary_prompt = f"""你是一個對話摘要專家。請根據以下對話歷史生成簡潔的摘要。

# 已有摘要
{current_summary if current_summary else "無"}

# 完整對話歷史
"""

    # 提取所有對話內容
    conversation_text = []
    for msg in messages:
        if hasattr(msg, "type"):
            if msg.type == "human":
                conversation_text.append(f"用戶: {msg.content}")
            elif msg.type == "ai":
                # 只提取文本內容，忽略工具調用
                if isinstance(msg.content, str) and msg.content:
                    conversation_text.append(f"助手: {msg.content}")

    summary_prompt += "\n".join(conversation_text)
    summary_prompt += """

# 摘要要求
- 總結用戶的核心需求和購物意圖
- 記錄所有討論過的商品（ID、名稱、類別）
- 記錄用戶的偏好和決策（喜歡/不喜歡的特性）
- 記錄已完成的操作（加購、結賬、設置提醒等）
- 保持結構化（使用列表）
- 控制長度（不超過 500 字）
- 如果有已有摘要，進行增量更新（不重複舊信息）

請直接輸出摘要內容："""

    # 調用 LLM 生成摘要（帶 LangFuse 觀測）
    print(f"🚀 [Compressor] 調用 Claude 生成摘要...")

    # 记录输入
    llm_logger.info("="*80)
    llm_logger.info(f"🔵 [LLM INPUT - COMPRESSOR] Session: {state.get('session_id', 'unknown')}")
    llm_logger.info("="*80)
    llm_logger.info(f"Summary Prompt:\n{summary_prompt}")
    llm_logger.info("="*80)

    try:
        callbacks = get_langfuse_callbacks()
        config = {"callbacks": callbacks} if callbacks else {}
        response = model.invoke([HumanMessage(content=summary_prompt)], config=config)
        new_summary = response.content

        # 记录输出
        llm_logger.info("="*80)
        llm_logger.info(f"🟢 [LLM OUTPUT - COMPRESSOR] Session: {state.get('session_id', 'unknown')}")
        llm_logger.info("="*80)
        llm_logger.info(f"Generated Summary ({len(new_summary)} chars):\n{new_summary}")
        llm_logger.info("="*80)
        llm_logger.info("")

        print(f"✅ [Compressor] 摘要已生成")
        print(f"   長度: {len(new_summary)} 字符")
        print(f"   預覽: {new_summary[:100]}...")
    except Exception as e:
        print(f"⚠️  [Compressor] 摘要生成失敗: {e}")
        llm_logger.error(f"Summary generation failed: {e}")
        new_summary = current_summary

    # 刪除舊消息，只保留最近 10 條
    KEEP_RECENT = 10
    messages_to_remove = [
        RemoveMessage(id=m.id)
        for m in messages[:-KEEP_RECENT]
        if hasattr(m, "id") and m.id
    ]

    removed_count = len(messages_to_remove)
    kept_count = min(KEEP_RECENT, len(messages))

    print(f"🗑️  [Compressor] 消息清理:")
    print(f"   刪除: {removed_count} 條")
    print(f"   保留: {kept_count} 條（最近）")
    print("="*80)
    print("🗜️  [CONTEXT COMPRESSOR] 執行完成\n")

    return {
        "summary": new_summary,
        "messages": messages_to_remove
    }


def handle_archive(state: ShopBotState) -> dict:
    """
    處理歸檔請求 - Agent 主動歸檔對話

    功能：
    - 提取 Agent 的歸檔摘要
    - 壓縮消息列表（刪除舊對話，保留摘要和最近 3 條）
    - 返回工具結果

    Args:
        state: 當前狀態

    Returns:
        更新後的狀態（包含壓縮後的消息和工具結果）
    """
    print("\n" + "="*80)
    print("📦 [HANDLE ARCHIVE] Agent 主動歸檔對話")
    print("="*80)

    messages = state["messages"]
    print(f"📊 [Archive] 當前消息數: {len(messages)} 條")

    last_msg = messages[-1]

    # 提取歸檔工具調用參數
    archive_call = next(
        tc for tc in last_msg.tool_calls
        if tc["name"] == "archive_previous_conversation"
    )
    summary = archive_call["args"]["summary"]

    print(f"📝 [Archive] 歸檔摘要:")
    print(f"   {summary[:200]}...")

    # 壓縮消息列表
    # 保留：AI 歸檔消息 + 最近 3 條消息
    compressed = [
        AIMessage(content=f"📋 之前對話總結：{summary}"),
        *messages[-3:]  # 保留最近 3 條（包括當前的歸檔調用）
    ]

    print(f"🗜️  [Archive] 壓縮後消息數: {len(compressed)} 條")

    # 返回工具結果
    tool_result = ToolMessage(
        content=f"✅ 已歸檔：{summary}",
        tool_call_id=archive_call["id"]
    )

    print("="*80)
    print("📦 [HANDLE ARCHIVE] 執行完成\n")

    return {"messages": compressed + [tool_result]}


def should_continue(state: ShopBotState) -> Literal["tools", "compress", "archive", "end"]:
    """
    條件函數 - 決定下一步動作

    決策邏輯（優先級從高到低）：
    1. 如果有歸檔工具調用 → "archive"（Agent 主動歸檔）
    2. 如果有其他工具調用 → "tools"
    3. 如果 context token > 800K → "compress"（被動壓縮，兜底）
    4. 否則 → "end"

    Args:
        state: 當前狀態

    Returns:
        "tools" | "compress" | "archive" | "end"
    """
    print("\n" + "="*80)
    print("🔀 [SHOULD_CONTINUE] 決策下一步動作")
    print("="*80)

    last_message = state["messages"][-1]

    # 優先檢查工具調用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        print(f"🔧 [Decision] 檢測到工具調用: {tool_names}")

        # 特殊：檢查是否是歸檔工具
        if any(tc["name"] == "archive_previous_conversation"
               for tc in last_message.tool_calls):
            print(f"📦 [Decision] → 'archive'（Agent 主動歸檔）")
            print("="*80 + "\n")
            return "archive"

        print(f"🔧 [Decision] → 'tools'（執行 {len(tool_names)} 個工具）")
        print("="*80 + "\n")
        return "tools"

    # 檢查是否需要壓縮 context（閾值：800K tokens，兜底機制）
    COMPRESSION_THRESHOLD = 800_000  # 800K tokens
    total_tokens = count_tokens(state["messages"])
    print(f"📊 [Decision] 當前 Token: {total_tokens:,} / {COMPRESSION_THRESHOLD:,}")

    if total_tokens > COMPRESSION_THRESHOLD:
        print(f"⚠️  [Decision] Token 超過閾值!")
        print(f"🗜️  [Decision] → 'compress'（觸發壓縮）")
        print("="*80 + "\n")
        return "compress"

    # 否則結束
    print(f"✅ [Decision] → 'end'（對話完成）")
    print("="*80 + "\n")
    return "end"


# ============================================
# Tool Execution Wrapper (with Logging)
# ============================================

def tools_node_with_logging(state: ShopBotState) -> dict:
    """
    工具執行節點（帶詳細日誌）

    包裝 ToolNode，在執行前後打印詳細日誌

    Args:
        state: 當前狀態

    Returns:
        更新後的狀態
    """
    print("\n" + "="*80)
    print("🔧 [TOOLS NODE] 開始執行工具")
    print("="*80)

    # 提取工具調用
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else []

    print(f"📋 [Tools] 待執行工具數: {len(tool_calls)}")
    for i, tc in enumerate(tool_calls, 1):
        print(f"\n🔧 [Tool {i}] {tc['name']}")
        print(f"   參數: {tc.get('args', {})}")

    # 執行工具
    tool_node = ToolNode(ALL_SHOPBOT_TOOLS)
    result = tool_node.invoke(state)

    # 打印結果
    if "messages" in result:
        tool_messages = result["messages"]
        print(f"\n✅ [Tools] 執行完成，返回 {len(tool_messages)} 條 ToolMessage")
        for i, msg in enumerate(tool_messages, 1):
            content_preview = msg.content[:150] if hasattr(msg, "content") else ""
            print(f"   [結果 {i}] {content_preview}...")

    print("="*80)
    print("🔧 [TOOLS NODE] 執行完成\n")

    return result


# ============================================
# Agent Creation
# ============================================

_agent_instance = None  # 單例
_agent_lock = None  # 異步鎖


async def get_agent():
    """
    獲取 ShopBot Agent 實例（單例模式，異步）

    使用手動定義的 StateGraph，支持：
    - ReAct 循環（agent → tools → agent）
    - Checkpointer（會話持久化）
    - Store（長期存儲）
    - 動態 System Prompt

    Returns:
        CompiledGraph: 編譯後的 Agent Graph
    """
    global _agent_instance, _agent_lock
    import asyncio

    # 初始化鎖（只在第一次調用時）
    if _agent_lock is None:
        _agent_lock = asyncio.Lock()

    # 雙重檢查鎖定
    if _agent_instance is not None:
        return _agent_instance

    async with _agent_lock:
        # 再次檢查（可能在等待鎖時已被其他協程創建）
        if _agent_instance is not None:
            return _agent_instance

        # 創建 StateGraph
        print("🏗️  [Init] 構建 LangGraph...")
        graph = StateGraph(ShopBotState)

        # 添加節點
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tools_node_with_logging)  # 使用帶日誌的包裝
        graph.add_node("context_compressor", context_compressor)
        graph.add_node("handle_archive", handle_archive)  # 歸檔節點
        print("✅ [Init] 已添加 4 個節點: agent, tools, context_compressor, handle_archive")

        # 添加邊
        print("🔗 [Init] 添加邊和條件路由...")
        graph.add_edge(START, "agent")
        graph.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                "archive": "handle_archive",       # Agent 主動歸檔
                "compress": "context_compressor",  # 當 token > 800K 時壓縮（兜底）
                "end": END
            }
        )
        graph.add_edge("tools", "agent")  # 工具執行後回到 agent
        graph.add_edge("handle_archive", "agent")  # 歸檔後回到 agent
        graph.add_edge("context_compressor", END)  # 壓縮完成後結束（下次調用時自動注入摘要）
        print("✅ [Init] Graph 結構已構建")

        # 創建持久化存儲（異步）
        print("💾 [Init] 初始化 Checkpointer...")
        checkpointer = await create_checkpointer()
        print("✅ [Init] Checkpointer 已就緒")

        # 編譯 Graph（Middleware 在這裡配置）
        print("⚙️  [Init] 編譯 Graph...")
        _agent_instance = graph.compile(
            checkpointer=checkpointer,
            # store=store,  # Store 目前不需要在編譯時傳入
        )
        print("✅ [Init] ShopBot Agent 已就緒!")
        print("="*80 + "\n")

        return _agent_instance


# ============================================
# Helper Functions
# ============================================

def generate_session_id() -> str:
    """生成唯一的 session ID"""
    import uuid
    return f"session_{uuid.uuid4().hex[:16]}"
