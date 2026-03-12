"""Memory client for Bedrock AgentCore short-term conversation memory.

Provides a thin wrapper around the bedrock-agentcore SDK's MemorySessionManager,
with graceful degradation — all operations catch exceptions, log warnings, and
continue so the agent always works even if memory is unavailable.
"""

import logging
from typing import Optional

from bedrock_agentcore.memory import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

logger = logging.getLogger(__name__)


class MemoryClient:
    """Thin wrapper around AgentCore Memory for conversation history."""

    def __init__(self, memory_id: str, region_name: Optional[str] = None):
        """Initialize with memory resource ID from config.

        Args:
            memory_id: Bedrock AgentCore memory resource identifier.
            region_name: AWS region override; defaults to SDK/env resolution.
        """
        self._memory_id = memory_id
        self._manager = MemorySessionManager(
            memory_id=memory_id,
            region_name=region_name,
        )
        logger.info("MemoryClient initialized with memory_id=%s", memory_id)

    def get_history(
        self,
        session_id: str,
        actor_id: str = "user",
        last_k: int = 10,
    ) -> list[dict]:
        """Retrieve last K conversation turns for a session.

        Returns a flat list of message dicts with ``role`` and ``content`` keys.
        Returns an empty list on any error (graceful degradation).
        """
        try:
            turns = self._manager.get_last_k_turns(
                actor_id=actor_id,
                session_id=session_id,
                k=last_k,
            )
            # Flatten turns (List[List[EventMessage]]) into a simple list of dicts
            messages: list[dict] = []
            for turn in turns:
                for msg in turn:
                    messages.append({
                        "role": msg.get("role", ""),
                        "content": msg.get("content", {}).get("text", ""),
                    })
            return messages
        except Exception:
            logger.warning(
                "Failed to retrieve conversation history for session=%s; "
                "proceeding without history.",
                session_id,
                exc_info=True,
            )
            return []

    def store_turn(
        self,
        session_id: str,
        actor_id: str,
        role: str,
        content: str,
    ) -> None:
        """Store a single conversation turn. Logs warning on error.

        Args:
            session_id: Conversation session identifier.
            actor_id: Actor identifier (e.g. ``"user"`` or ``"assistant"``).
            role: Message role — ``"user"`` or ``"assistant"``.
            content: Message text.
        """
        try:
            message_role = MessageRole(role.upper())
            self._manager.add_turns(
                actor_id=actor_id,
                session_id=session_id,
                messages=[ConversationalMessage(text=content, role=message_role)],
            )
        except Exception:
            logger.warning(
                "Failed to store turn for session=%s role=%s; "
                "continuing without persisting this turn.",
                session_id,
                role,
                exc_info=True,
            )
