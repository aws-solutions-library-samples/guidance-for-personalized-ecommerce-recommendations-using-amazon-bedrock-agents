#!/usr/bin/env python3
"""为 Mock 环境创建测试对话数据

用法：
    python mock_conversation.py

这个脚本会：
1. 创建一个 mock session
2. 插入几条测试对话
3. 触发后台更新
4. 展示更新结果
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage


async def create_mock_conversation():
    """创建 mock 对话并测试更新"""
    from app.agent import get_agent

    print("=" * 60)
    print("🎭 Mock 对话环境测试")
    print("=" * 60)

    # 配置
    user_id = "user_001"
    session_id = "mock_session_20260317"

    print(f"\n📋 配置:")
    print(f"  User ID: {user_id}")
    print(f"  Session ID: {session_id}")

    # 获取 Agent
    print("\n🔧 初始化 Agent...")
    agent = await get_agent()

    # 模拟对话
    conversations = [
        {
            "user": "我想买个高端手机",
            "expected_insight": "偏好高端产品"
        },
        {
            "user": "有 Apple 的吗？",
            "expected_insight": "明确偏好 Apple 品牌"
        },
        {
            "user": "价格在 8000 左右",
            "expected_insight": "价格范围 8000 元"
        },
        {
            "user": "我对拍照要求比较高",
            "expected_insight": "重视拍照功能"
        },
    ]

    print("\n💬 模拟对话:")
    config = {"configurable": {"thread_id": session_id}}

    for i, conv in enumerate(conversations, 1):
        print(f"\n  [{i}] 用户: {conv['user']}")

        # 调用 Agent
        result = agent.invoke(
            {
                "messages": [HumanMessage(content=conv["user"])],
                "user_id": user_id,
                "session_id": session_id,
            },
            config=config
        )

        # 提取 AI 回复
        ai_message = None
        for msg in reversed(result["messages"]):
            if msg.type == "ai" and isinstance(msg.content, str):
                ai_message = msg.content
                break

        print(f"      AI: {ai_message[:100] if ai_message else '(无回复)'}...")
        print(f"      预期洞察: {conv['expected_insight']}")

    print("\n" + "=" * 60)
    print("🔄 触发后台画像更新...")
    print("=" * 60)

    # 触发后台更新
    from app.background_profile_updater import background_profile_update
    await background_profile_update(session_id, user_id)

    # 查看更新结果
    print("\n" + "=" * 60)
    print("📊 更新后的用户画像:")
    print("=" * 60)

    profile_path = Path(f"data/user_profiles/{user_id}.json")
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
            print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print("  (画像文件不存在)")

    print("\n" + "=" * 60)
    print("✅ Mock 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(create_mock_conversation())
