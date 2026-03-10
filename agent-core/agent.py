from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from tools import search_product, compare_product, get_recommendation
from config import Config

app = BedrockAgentCoreApp()
config = Config.load()

SYSTEM_PROMPT = """You are a professional sales expert which can help customer on:
1. Search products based on customer conditions and requirements.
2. Compare products using user history, preferences, and demographics.
3. Generate personalized product recommendations based on user profile.
4. Respond to the customer in the same language they use."""

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[search_product, compare_product, get_recommendation],
    model="bedrock/" + config.model_id,
)

@app.entrypoint
async def invoke(payload=None):
    prompt = (payload.get("prompt", "Hello! How can I help you today?")
              if payload else "Hello! How can I help you today?")
    result = agent(prompt)
    return {"result": str(result)}

if __name__ == "__main__":
    app.run()
