"""后台用户画像更新 Agent

功能：
- 在 session idle 30 秒后自动触发（测试用，生产环境建议 30 分钟 = 1800 秒）
- 分析对话历史，提取用户特征
- 更新用户画像（Semantic, Procedural, Episodic Memory）
- 不打断主对话流程
"""
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrockConverse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import create_react_agent

# 加载环境变量
load_dotenv()


# ============================================
# 后台工具（仅后台 Agent 使用）
# ============================================

@tool
def read_user_profile_bg(user_id: str) -> dict:
    """
    读取用户画像（后台专用）

    Args:
        user_id: 用户 ID

    Returns:
        用户画像字典
    """
    profile_path = Path(__file__).parent.parent / "data" / "user_profiles" / f"{user_id}.json"

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
            return json.load(f)
    except Exception as e:
        print(f"⚠️  读取用户画像失败 ({user_id}): {e}")
        return {
            "user_id": user_id,
            "updated_at": datetime.now().isoformat(),
            "explicit_preferences": "",
            "inferred_preferences": "",
            "stylistic_notes": "",
            "successful_patterns": "",
            "things_to_avoid": ""
        }


@tool
def update_user_profile_batch(user_id: str, updates: List[Dict[str, str]]) -> str:
    """
    批量更新用户画像（后台专用）

    Args:
        user_id: 用户 ID
        updates: 更新列表，每个元素包含:
            - section: explicit_preferences/inferred_preferences/stylistic_notes/successful_patterns/things_to_avoid
            - action: "append" 或 "replace"
            - content: 新内容

    Returns:
        成功消息

    示例:
        updates = [
            {
                "section": "explicit_preferences",
                "action": "append",
                "content": "- 喜欢 Apple 品牌"
            },
            {
                "section": "inferred_preferences",
                "action": "append",
                "content": "- 决策谨慎，喜欢详细对比"
            }
        ]
    """
    # 读取当前画像
    profile = read_user_profile_bg.invoke({"user_id": user_id})

    # 应用更新
    for update in updates:
        section = update.get("section")
        action = update.get("action")
        content = update.get("content")

        if not section or not action or not content:
            continue

        if action == "append":
            if profile.get(section):
                profile[section] += f"\n{content}"
            else:
                profile[section] = content
        elif action == "replace":
            profile[section] = content

    # 更新时间戳
    profile["updated_at"] = datetime.now().isoformat()

    # 保存
    profile_path = Path(__file__).parent.parent / "data" / "user_profiles" / f"{user_id}.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return f"✅ 已更新用户 {user_id} 的画像，共 {len(updates)} 项更新"
    except Exception as e:
        return f"❌ 更新失败: {e}"


@tool
async def read_session_messages_bg(session_id: str) -> List[Dict]:
    """
    读取 session 的对话历史（从 LangGraph checkpoint）

    Args:
        session_id: Session ID（即 thread_id）

    Returns:
        消息列表
    """
    import aiosqlite

    try:
        # 正确创建 AsyncSqliteSaver
        conn = await aiosqlite.connect("data/shopbot.db")
        checkpointer = AsyncSqliteSaver(conn)
        await checkpointer.setup()

        # 获取 thread 的 checkpoint
        config = {"configurable": {"thread_id": session_id}}
        checkpoint = await checkpointer.aget(config)

        if not checkpoint:
            print(f"ℹ️  Session {session_id} 没有对话历史")
            return []

        # 提取 messages
        messages = checkpoint.get("channel_values", {}).get("messages", [])

        if not messages:
            print(f"ℹ️  Session {session_id} 消息列表为空")
            return []

        result = []
        for msg in messages:
            # 只提取用户和 AI 的消息，忽略工具消息
            if hasattr(msg, "type") and msg.type in ["human", "ai"]:
                msg_dict = {
                    "role": msg.type,
                    "content": msg.content if hasattr(msg, "content") else "",
                }
                result.append(msg_dict)

        print(f"✅ 成功读取 {len(result)} 条对话消息")
        return result
    except Exception as e:
        print(f"⚠️  读取对话历史失败 ({session_id}): {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================
# 后台更新逻辑
# ============================================

async def background_profile_update(session_id: str, user_id: str):
    """
    后台更新用户画像

    使用 create_react_agent 自动执行工具调用链：
    1. 读取当前画像
    2. 读取对话历史
    3. 分析并更新画像

    Args:
        session_id: Session ID
        user_id: 用户 ID
    """
    print(f"🔄 [后台更新] 开始更新画像：session={session_id}, user={user_id}")

    try:
        # 创建 LLM
        model = ChatBedrockConverse(
            model=os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            temperature=0.3,
        )

        # 后台工具列表
        background_tools = [read_user_profile_bg, update_user_profile_batch, read_session_messages_bg]

        # 创建 ReAct Agent（会自动执行工具循环）
        bg_agent = create_react_agent(model, background_tools)

        # 构建后台分析 Prompt
        prompt = f"""# 任务：分析对话并更新用户画像

你是一个后台分析 Agent，负责从对话中学习用户特征。

## 第一步：读取当前画像
调用 read_user_profile_bg("{user_id}") 获取当前用户画像

## 第二步：读取对话历史
调用 read_session_messages_bg("{session_id}") 获取本次对话

**重要**：如果对话历史为空或读取失败，说明这是一个新 session 或 mock 环境，请跳过分析直接返回"暂无新信息需要更新"。

## 第三步：分析并提取信息（仅在有对话历史时）

分析对话，提取以下信息：

1. **Semantic Memory（偏好）**：
   - 用户明确说了什么新的偏好？（explicit_preferences）
   - 从行为推断出什么新的偏好？（inferred_preferences）

2. **Procedural Memory（风格）**：
   - 用户的沟通风格有什么特点？（stylistic_notes）

3. **Episodic Memory（经验）**：
   - 有什么成功的互动？（用户满意、购买、加购物车）→ successful_patterns
   - 有什么失败的互动？（用户不满、流失、抱怨）→ things_to_avoid

## 第四步：更新画像（如果有新发现）

调用 update_user_profile_batch 更新。

示例:
```python
update_user_profile_batch(
    user_id="{user_id}",
    updates=[
        {{
            "section": "explicit_preferences",
            "action": "append",
            "content": "- 喜欢 Apple 品牌"
        }},
        {{
            "section": "inferred_preferences",
            "action": "append",
            "content": "- 决策谨慎，喜欢详细对比"
        }}
    ]
)
```

## 注意
- 只提取**稳定的、重要的**信息
- 要考虑当前画像，避免重复
- 如果没有新发现或对话历史为空，直接返回"暂无新信息需要更新"

开始分析！
"""

        # 调用 Agent（异步方式，会自动循环执行工具）
        result = await bg_agent.ainvoke({
            "messages": [HumanMessage(content=prompt)]
        })

        print(f"✅ [后台更新] 完成：session={session_id}, user={user_id}")
        print(f"📊 [后台更新] Agent 执行了 {len(result.get('messages', []))} 步操作")

    except Exception as e:
        print(f"❌ [后台更新] 失败：{e}")
        import traceback
        traceback.print_exc()


# ============================================
# 手动触发（用于测试）
# ============================================

async def manual_update(session_id: str, user_id: str):
    """
    手动触发画像更新（用于测试）

    Args:
        session_id: Session ID
        user_id: 用户 ID
    """
    await background_profile_update(session_id, user_id)


if __name__ == "__main__":
    # 测试
    print("测试后台更新...")
    asyncio.run(manual_update("test_session", "user_001"))
