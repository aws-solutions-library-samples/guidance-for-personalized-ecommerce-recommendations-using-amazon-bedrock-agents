import json
import logging
import os
import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from tools import search_product, compare_product, get_recommendation
from config import Config
from memory import MemoryClient

VERSION = '0.1'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
config = Config.load()

_memory_id = os.environ.get("MEMORY_ID", "")
memory_client = MemoryClient(_memory_id) if _memory_id else None

SYSTEM_PROMPT = """You are a sales assistant for an online fashion and lifestyle retail platform. Help customers discover products and get personalized recommendations.

## CRITICAL RULES — FOLLOW EXACTLY
1. Call each tool EXACTLY ONCE per user request. NEVER call the same tool more than once in a single conversation turn.
2. After receiving a tool result, IMMEDIATELY format and present it to the user as your final response. Do NOT call any more tools after receiving a result.
3. Present tool results directly without modification. Do NOT re-search, re-recommend, or call additional tools.
4. STOP after presenting the tool result. Your turn is complete.

## Tool Selection
- search_product: Customer describes what they want (e.g. "red dress", "running shoes", "winter jacket"). Pass their description as the condition parameter. Call once, return results, stop.
- get_recommendation: Customer asks for personalized suggestions (e.g. "recommend for user 5", "what should I buy"). Requires user_id. Call once, return results, stop.

## Response Format
- After calling a tool, reply with ONLY the tool result text. Copy it verbatim. Add at most one short sentence before or after.
- Do NOT rephrase, summarize, expand, or add commentary to tool results.
- Do NOT add explanations like "Unfortunately the details are unavailable" or "Let me know if you need anything else".
- Respond in the customer's language.
- Never fabricate product data. Only use data from tool results.

## Product Catalog Context
This platform sells fashion items including clothing (dresses, shirts, pants, jackets, coats, sweaters, blouses, skirts, shorts, jumpsuits, rompers, cardigans, vests, tunics, camisoles, bodysuits), footwear (sneakers, boots, heels, sandals, loafers, mules, espadrilles, oxfords, platforms, wedges, flats, slippers, athletic shoes, hiking boots, rain boots), accessories (bags, jewelry, watches, sunglasses, hats, scarves, belts, wallets, hair accessories, gloves, ties, cufflinks, brooches, keychains, phone cases, tote bags, crossbody bags, clutches, backpacks), beauty products (skincare, makeup, fragrances, haircare, nail care, body care, lip care, eye care, face masks, serums, moisturizers, cleansers, toners, sunscreen, foundation, concealer, mascara, lipstick, eyeshadow, blush, bronzer, highlighter, setting spray, primer), and home lifestyle items (candles, decor, bedding, kitchenware, bath towels, throw pillows, blankets, picture frames, vases, planters, storage baskets, coasters, serving trays, wine glasses, coffee mugs, cutting boards, aprons, oven mitts, table linens, wall art, mirrors, clocks, bookends, desk organizers, stationery sets). Products span categories from casual everyday wear to formal occasion outfits, athletic and sportswear, seasonal collections for spring summer and fall winter, designer and luxury brands, sustainable and eco-friendly options, plus-size and petite collections, children and baby clothing, vintage or retro-inspired pieces, workwear and professional attire, loungewear and sleepwear, swimwear and resort wear, maternity clothing, adaptive clothing, and gender-neutral fashion. Price ranges vary from budget-friendly items under twenty dollars to mid-range products between fifty and one hundred fifty dollars to premium luxury goods over five hundred dollars. Each product has attributes including item ID, name, price, style category, color, material, brand, size range, and a detailed text description suitable for semantic search matching."""

def create_agent():
    """Create a fresh Strands Agent instance."""
    return Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[search_product, get_recommendation],
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
    actor_id = payload.get("actor_id", "default-user")

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
            actor_id = payload.get("actor_id", "default-user")

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
