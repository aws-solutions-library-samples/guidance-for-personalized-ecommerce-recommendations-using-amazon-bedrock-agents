"""ShopBot FastAPI 應用"""
import os
import json
from typing import AsyncIterator, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrockConverse

# 導入模型和 Agent
from app.models.data import ChatRequest, ChatResponse, HistoryResponse
from app.agent import get_agent, generate_session_id

# 載入環境變數
load_dotenv()

# ============================================
# Session 活動追踪（用於 30 分鐘 idle 檢測）
# ============================================
session_activity = {}  # {session_id: {"user_id": str, "last_time": datetime, "updated": bool}}

# 創建 FastAPI 應用
api = FastAPI(
    title="ShopBot API",
    description="E-commerce Shopping Agent powered by LangGraph + AWS Bedrock Claude",
    version="1.0.0"
)

# 添加 CORS 中間件（前後端分離）
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境應該限制具體域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 掛載靜態文件目錄（前端）
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    api.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# ============================================
# 啟動事件
# ============================================

@api.on_event("startup")
async def startup_event():
    """啟動時預熱 Agent"""
    print("🚀 預熱 ShopBot Agent...")
    try:
        await get_agent()
        print("✅ Agent 已就緒！")
    except Exception as e:
        print(f"⚠️  Agent 預熱失敗: {e}")


# ============================================
# 基礎端點
# ============================================

@api.get("/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "service": "ShopBot",
        "timestamp": datetime.utcnow().isoformat()
    }


@api.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    非流式聊天端點

    Args:
        request: ChatRequest (query, user_id, session_id)
        background_tasks: FastAPI 後台任務

    Returns:
        ChatResponse with message and state snapshot
    """
    # 生成 session_id（如果未提供）
    session_id = request.session_id or generate_session_id()
    current_time = datetime.now()

    # ============================================
    # 檢查是否需要觸發後台畫像更新（30 秒 idle，測試用）
    # ============================================
    if session_id in session_activity:
        session_info = session_activity[session_id]
        last_time = session_info["last_time"]
        time_diff = (current_time - last_time).total_seconds()

        # 如果距離上次活動 > 30 秒，且本 session 尚未更新（測試用）
        if time_diff > 30 and not session_info.get("updated", False):
            print(f"⏰ [後台更新] Session {session_id} idle {time_diff:.1f} 秒，觸發畫像更新")
            from app.background_profile_updater import background_profile_update
            background_tasks.add_task(background_profile_update, session_id, request.user_id)
            session_info["updated"] = True  # 標記為已更新，避免重複觸發

    # 更新活動時間
    session_activity[session_id] = {
        "user_id": request.user_id,
        "last_time": current_time,
        "updated": session_activity.get(session_id, {}).get("updated", False)
    }

    try:
        # 獲取 Agent（異步）
        agent = await get_agent()

        # 構建初始狀態
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "session_id": session_id,
        }

        # 配置（用於持久化）
        config = {
            "configurable": {
                "thread_id": session_id  # 使用 session_id 作為 thread_id
            }
        }

        # 調用 Agent（非流式）
        result = agent.invoke(initial_state, config=config)

        # 提取最後一條 AI 消息
        ai_message = None
        for msg in reversed(result["messages"]):
            if msg.type == "ai":
                ai_message = msg.content
                break

        if ai_message is None:
            raise HTTPException(status_code=500, detail="Agent 未返回有效響應")

        # 構建響應
        return ChatResponse(
            message=ai_message,
            session_id=session_id,
            user_id=request.user_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"處理請求時出錯: {str(e)}")


# ============================================
# 流式端點
# ============================================

async def generate_stream(
    agent,
    initial_state: dict,
    config: dict
) -> AsyncIterator[str]:
    """
    生成 SSE 流

    Yields:
        SSE 格式的事件流
    """
    try:
        # 使用 astream_events 獲取流式輸出
        async for event in agent.astream_events(initial_state, config=config, version="v2"):
            event_type = event.get("event")

            # 過濾我們關心的事件
            if event_type == "on_chat_model_stream":
                # LLM 輸出流
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # 提取實際文本內容
                    text_content = ""

                    if isinstance(chunk.content, str):
                        # 簡單字符串
                        text_content = chunk.content
                    elif isinstance(chunk.content, list):
                        # 數組格式：提取所有 text 字段
                        for item in chunk.content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_content += item.get("text", "")
                            elif isinstance(item, str):
                                text_content += item
                    elif isinstance(chunk.content, dict) and chunk.content.get("text"):
                        # 對象格式
                        text_content = chunk.content.get("text", "")

                    # 只有在有文本內容時才發送
                    if text_content:
                        data = {
                            "type": "content",
                            "content": text_content
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            elif event_type == "on_tool_start":
                # 工具調用開始
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                data = {
                    "type": "tool_start",
                    "tool": tool_name,
                    "input": tool_input
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            elif event_type == "on_tool_end":
                # 工具調用結束
                tool_name = event.get("name", "unknown")
                data = {
                    "type": "tool_end",
                    "tool": tool_name
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 流結束
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    except Exception as e:
        # 錯誤處理
        error_data = {
            "type": "error",
            "error": str(e)
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@api.post("/chat/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    流式聊天端點（SSE）

    Args:
        request: ChatRequest (query, user_id, session_id)
        background_tasks: FastAPI 後台任務

    Returns:
        StreamingResponse with SSE events
    """
    # 生成 session_id（如果未提供）
    session_id = request.session_id or generate_session_id()
    current_time = datetime.now()

    # ============================================
    # 檢查是否需要觸發後台畫像更新（30 秒 idle，測試用）
    # ============================================
    if session_id in session_activity:
        session_info = session_activity[session_id]
        last_time = session_info["last_time"]
        time_diff = (current_time - last_time).total_seconds()

        # 如果距離上次活動 > 30 秒，且本 session 尚未更新（測試用）
        if time_diff > 30 and not session_info.get("updated", False):
            print(f"⏰ [後台更新] Session {session_id} idle {time_diff:.1f} 秒，觸發畫像更新")
            from app.background_profile_updater import background_profile_update
            background_tasks.add_task(background_profile_update, session_id, request.user_id)
            session_info["updated"] = True  # 標記為已更新，避免重複觸發

    # 更新活動時間
    session_activity[session_id] = {
        "user_id": request.user_id,
        "last_time": current_time,
        "updated": session_activity.get(session_id, {}).get("updated", False)
    }

    try:
        # 獲取 Agent（異步）
        agent = await get_agent()

        # 構建初始狀態
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "session_id": session_id,
        }

        # 配置（用於持久化）
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }

        # 返回流式響應
        return StreamingResponse(
            generate_stream(agent, initial_state, config),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Nginx 兼容
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"處理流式請求時出錯: {str(e)}")


# ============================================
# 會話管理端點
# ============================================

@api.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    """
    獲取會話歷史

    Args:
        session_id: 會話ID

    Returns:
        HistoryResponse with message history
    """
    try:
        from app.models.persistence import create_checkpointer

        checkpointer = create_checkpointer()
        config = {"configurable": {"thread_id": session_id}}

        # 獲取最新狀態
        state = checkpointer.get(config)

        if state is None:
            raise HTTPException(status_code=404, detail=f"會話 {session_id} 不存在")

        # 提取消息
        messages = []
        for msg in state.values.get("messages", []):
            messages.append({
                "type": msg.type,
                "content": msg.content,
                "timestamp": getattr(msg, "additional_kwargs", {}).get("timestamp", "")
            })

        return HistoryResponse(
            session_id=session_id,
            messages=messages,
            message_count=len(messages)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取歷史時出錯: {str(e)}")


@api.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    刪除會話（清除持久化數據）

    Args:
        session_id: 會話ID

    Returns:
        Success message
    """
    try:
        # 注意：SqliteSaver 不直接支持刪除
        # 這裡我們返回成功，但實際上數據仍在 DB 中
        # 生產環境應該實現真正的刪除邏輯
        return {
            "success": True,
            "message": f"會話 {session_id} 已標記刪除（Mock 實現）"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除會話時出錯: {str(e)}")


# ============================================
# 商品相關端點
# ============================================

@api.get("/api/products")
async def get_products():
    """
    獲取商品列表

    Returns:
        商品列表 JSON
    """
    try:
        # 讀取商品數據文件
        products_file = Path(__file__).parent.parent / "data" / "products_display.json"

        if not products_file.exists():
            raise HTTPException(status_code=404, detail="商品數據文件不存在")

        with open(products_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取商品列表時出錯: {str(e)}")


@api.get("/api/suggested-questions/{product_id}")
async def get_suggested_questions(product_id: str):
    """
    根據商品 ID 生成推薦問題

    Args:
        product_id: 商品 ID

    Returns:
        推薦問題列表
    """
    try:
        # 讀取商品數據
        products_file = Path(__file__).parent.parent / "data" / "products_display.json"

        if not products_file.exists():
            raise HTTPException(status_code=404, detail="商品數據文件不存在")

        with open(products_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 查找商品
        product = None
        for p in data["products"]:
            if p["id"] == product_id:
                product = p
                break

        if product is None:
            raise HTTPException(status_code=404, detail=f"商品 {product_id} 不存在")

        # 使用 LLM 生成推薦問題
        questions = await generate_questions_for_product(product)

        return {
            "product_id": product_id,
            "product_title": product["title"],
            "questions": questions
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成推薦問題時出錯: {str(e)}")


async def generate_questions_for_product(product: dict) -> List[str]:
    """
    使用 LLM 為商品生成推薦問題

    Args:
        product: 商品信息字典

    Returns:
        推薦問題列表
    """
    try:
        # 創建 LLM
        model = ChatBedrockConverse(
            model=os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            temperature=0.7,
        )

        # 構建 prompt
        prompt = f"""你是一個電商購物助手。用戶點擊了以下商品，請生成 5 個用戶可能感興趣的問題。

# 商品信息
- 標題: {product['title']}
- 類別: {product['category']}
- 價格: {product['price']} 元
- 描述: {product['description']}
- 特性: {', '.join(product['features'])}

# 要求
1. 生成 5 個簡短、自然的問題（10-20字）
2. 問題應該針對用戶關心的點：性能、使用場景、性價比、售後等
3. 問題要具體，不要太泛泛
4. 直接輸出問題，每行一個，不要編號

示例格式：
這個手機殼是否防水防摔
支持無線充電嗎
有哪些顏色可選
和官方價格差多少
包裝裡有什麼配件

請直接輸出 5 個問題："""

        # 調用 LLM
        response = model.invoke([HumanMessage(content=prompt)])

        # 解析響應
        questions_text = response.content.strip()
        questions = [q.strip() for q in questions_text.split('\n') if q.strip()]

        # 確保返回 5 個問題
        if len(questions) < 5:
            # 如果不足，添加通用問題
            default_questions = [
                "這個商品的性價比怎麼樣？",
                "有什麼優惠活動嗎？",
                "售後服務如何？",
                "發貨時間大概多久？",
                "有實物圖片嗎？"
            ]
            questions.extend(default_questions[:5 - len(questions)])

        return questions[:5]

    except Exception as e:
        print(f"生成問題失敗: {e}")
        # 返回默認問題
        return [
            f"{product['title']}的性價比如何？",
            "有什麼優缺點？",
            "適合什麼使用場景？",
            "有優惠活動嗎？",
            "售後服務怎麼樣？"
        ]


# ============================================
# 用戶偏好端點
# ============================================

@api.get("/user/{user_id}/preferences")
async def get_user_preferences(user_id: str):
    """
    獲取用戶偏好

    Args:
        user_id: 用戶ID

    Returns:
        User preferences
    """
    try:
        from app.tools.other_tools import get_user_preferences as get_prefs_tool

        result_str = get_prefs_tool.invoke({"user_id": user_id})
        result = json.loads(result_str)

        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取用戶偏好時出錯: {str(e)}")


@api.put("/user/{user_id}/preferences")
async def update_user_preferences(user_id: str, preferences: dict):
    """
    更新用戶偏好

    Args:
        user_id: 用戶ID
        preferences: 偏好字典 (key-value pairs)

    Returns:
        Success message
    """
    try:
        from app.tools.other_tools import update_user_preference as update_pref_tool

        results = []
        for key, value in preferences.items():
            result_str = update_pref_tool.invoke({
                "user_id": user_id,
                "key": key,
                "value": value
            })
            results.append(json.loads(result_str))

        # 檢查是否有失敗
        failed = [r for r in results if not r.get("success")]
        if failed:
            raise HTTPException(status_code=400, detail=f"部分更新失敗: {failed}")

        return {
            "success": True,
            "message": f"已更新 {len(preferences)} 個偏好"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新用戶偏好時出錯: {str(e)}")


# ============================================
# 啟動配置
# ============================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "app.main:api",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
