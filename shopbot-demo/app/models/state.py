"""ShopBot State 定义"""
from typing import NotRequired, Annotated
from typing_extensions import TypedDict


def filter_completed_tool_calls(existing: list, new: list) -> list:
    """
    Custom reducer: 过滤已完成的工具调用链

    只过滤已完成的工具调用链（三段式）：
        AIMessage(tool_calls) → ToolMessage → AIMessage(最终回复)

    压缩为：
        AIMessage(最终回复)

    关键：
    - 只处理**已完成**的调用链（有最终 AI 回复）
    - 不处理**进行中**的工具调用（避免破坏 ReAct 循环）
    - Agent 执行期间仍能看到 ToolMessage（用于推理）

    Args:
        existing: 现有消息列表
        new: 新消息列表

    Returns:
        过滤后的消息列表
    """
    # 合并新旧消息
    all_messages = existing + new

    filtered = []
    i = 0

    while i < len(all_messages):
        msg = all_messages[i]

        # 检测完整的工具调用链（三段式）
        if (i + 2 < len(all_messages) and
            hasattr(msg, 'type') and msg.type == "ai" and
            getattr(msg, 'tool_calls', None) and
            hasattr(all_messages[i+1], 'type') and all_messages[i+1].type == "tool" and
            hasattr(all_messages[i+2], 'type') and all_messages[i+2].type == "ai"):

            # 只保留最后的 AI 回复，跳过前两条
            filtered.append(all_messages[i+2])
            i += 3
        else:
            # 保留其他消息（包括进行中的工具调用）
            filtered.append(msg)
            i += 1

    return filtered


class ShopBotState(TypedDict):
    """
    ShopBot Agent 的状态定义

    使用 TypedDict + 自定义 reducer 实现：
    - messages 字段使用 filter_completed_tool_calls reducer 自动过滤工具消息
    - 添加用户画像更新状态字段
    """
    # 核心字段
    messages: Annotated[list, filter_completed_tool_calls]  # 对话历史（自动过滤工具消息）
    user_id: str  # 用户 ID
    session_id: str  # 会话 ID（即 thread_id）

    # 可选字段
    summary: NotRequired[str]  # 对话摘要（动态生成，用于压缩历史）

    # 用户画像更新状态（用于后台更新机制）
    profile_update_status: NotRequired[str]  # "pending" | "processing" | "completed"
    profile_update_time: NotRequired[str]    # ISO timestamp
    last_message_time: NotRequired[str]      # ISO timestamp

    # ❌ 不需要的字段（设计原则：极简 State）
    # - cart: 通过工具动态获取
    # - browsing_history: 通过工具动态获取
    # - user_preferences: 通过工具动态获取
