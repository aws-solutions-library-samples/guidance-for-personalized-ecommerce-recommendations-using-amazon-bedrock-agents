import json
import logging
import os
import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from tools import search_product, compare_product, get_recommendation
from config import Config
from memory import MemoryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
config = Config.load()

_memory_id = os.environ.get("MEMORY_ID", "")
memory_client = MemoryClient(_memory_id) if _memory_id else None

SYSTEM_PROMPT = """You are a professional sales expert which can help customer on:
1. Search products based on customer conditions and requirements.
2. Compare products using user history, preferences, and demographics.
3. Generate personalized product recommendations based on user profile.
4. Respond to the customer in the same language they use."""


def create_agent():
    """Create a fresh Strands Agent instance."""
    return Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[search_product, compare_product, get_recommendation],
        model=config.model_id,
    )

def _build_history_context(history: list[dict]) -> str:
    """Format conversation history turns into a context string."""
    if not history:
        return ""
    lines = ["Previous conversation:"]
    for turn in history:
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        lines.append(f"  {role}: {content}")
    return "\n".join(lines)


@app.entrypoint
async def invoke(payload=None):
    prompt = (payload.get("prompt", "Hello! How can I help you today?")
              if payload else "Hello! How can I help you today?")
    logger.info("Received prompt: %s", prompt[:100])

    session_id = (payload.get("session_id") if payload else None) or str(uuid.uuid4())

    # Retrieve conversation history and prepend to prompt
    history_context = ""
    if memory_client is not None:
        history = memory_client.get_history(session_id)
        history_context = _build_history_context(history)

    full_prompt = f"{history_context}\n\n{prompt}" if history_context else prompt

    async def stream_response():
        try:
            agent = create_agent()
            result = agent(full_prompt)
            response_text = str(result)

            # Store both turns in memory
            if memory_client is not None:
                memory_client.store_turn(session_id, "user", "user", prompt)
                memory_client.store_turn(session_id, "assistant", "assistant", response_text)

            response = json.dumps({"result": response_text})
            logger.info("Agent response generated successfully")
            yield response
        except Exception as e:
            logger.exception("Agent invocation failed")
            yield json.dumps({"error": str(e)})

    return stream_response()


@app.websocket
async def ws_handler(websocket, context):
    """Handle WebSocket connections from AgentCore platform."""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            prompt = payload.get("prompt", "Hello! How can I help you today?")
            logger.info("WS received prompt: %s", prompt[:100])

            session_id = payload.get("session_id") or str(uuid.uuid4())

            # Retrieve conversation history and prepend to prompt
            history_context = ""
            if memory_client is not None:
                history = memory_client.get_history(session_id)
                history_context = _build_history_context(history)

            full_prompt = f"{history_context}\n\n{prompt}" if history_context else prompt

            try:
                agent = create_agent()
                result = agent(full_prompt)
                response_text = str(result)

                # Store both turns in memory
                if memory_client is not None:
                    memory_client.store_turn(session_id, "user", "user", prompt)
                    memory_client.store_turn(session_id, "assistant", "assistant", response_text)

                await websocket.send_text(json.dumps({"result": response_text}))
            except Exception as e:
                logger.exception("WS agent invocation failed")
                await websocket.send_text(json.dumps({"error": str(e)}))
    except Exception:
        pass


if __name__ == "__main__":
    app.run()
