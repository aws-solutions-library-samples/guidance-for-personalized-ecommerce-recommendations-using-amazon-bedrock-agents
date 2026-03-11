import json
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from tools import search_product, compare_product, get_recommendation
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
config = Config.load()

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


@app.entrypoint
async def invoke(payload=None):
    prompt = (payload.get("prompt", "Hello! How can I help you today?")
              if payload else "Hello! How can I help you today?")
    logger.info("Received prompt: %s", prompt[:100])

    async def stream_response():
        try:
            agent = create_agent()
            result = agent(prompt)
            response = json.dumps({"result": str(result)})
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
            try:
                agent = create_agent()
                result = agent(prompt)
                await websocket.send_text(json.dumps({"result": str(result)}))
            except Exception as e:
                logger.exception("WS agent invocation failed")
                await websocket.send_text(json.dumps({"error": str(e)}))
    except Exception:
        pass


if __name__ == "__main__":
    app.run()
