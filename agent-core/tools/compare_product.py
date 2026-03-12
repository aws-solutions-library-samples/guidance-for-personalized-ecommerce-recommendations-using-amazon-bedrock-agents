"""Product comparison tool with user profile enrichment and LLM summary.

Ported from lambda/handler.py compare_product() to use Strands @tool decorator
with shared helpers for DynamoDB lookups, embedding generation, and Bedrock LLM calls.
"""

import json
import logging

from strands import tool

from config import Config
from tools.helpers import (
    call_bedrock_llm,
    create_opensearch_client,
    get_embedding_for_text,
    get_item_info,
    get_user_info,
)

logger = logging.getLogger(__name__)

config = Config.load()


@tool
def compare_product(user_id: str, condition: str, preference: str) -> str:
    """Compare products for a user based on search condition and preferences.

    Args:
        user_id: The unique user identifier.
        condition: Text description of products to search for.
        preference: User's preferences for comparison.

    Returns:
        JSON with 'items' list and 'summarize' comparison text.
    """
    try:
        # --- Inline search logic (same as search_product) ---
        text_embedding = get_embedding_for_text(condition)
        if isinstance(text_embedding, str):
            return text_embedding

        client = create_opensearch_client(config)
        if isinstance(client, str):
            return client

        query = {
            "size": 5,
            "query": {
                "knn": {
                    "multimodal_vector": {
                        "vector": text_embedding,
                        "k": 5,
                    }
                }
            },
            "_source": [
                "item_id",
                "price",
                "style",
                "image_product_description",
                "image_path",
            ],
        }
        response = client.search(
            body=query, index="product-search-multimodal-index"
        )

        items = []
        for hit in response["hits"]["hits"]:
            items.append(
                {
                    "item_id": hit["_source"]["item_id"],
                    "score": hit["_score"],
                    "image": hit["_source"]["image_path"],
                    "price": hit["_source"]["price"],
                    "style": hit["_source"]["style"],
                    "description": hit["_source"]["image_product_description"],
                }
            )

        # --- User profile enrichment ---
        user = get_user_info(user_id, config)
        if isinstance(user, str):
            return user

        visted = []
        for item_id in user["visted"]:
            info = get_item_info(item_id, config)
            if isinstance(info, str):
                return info
            visted.append(info)

        add_to_cart = []
        for item_id in user["add_to_cart"]:
            info = get_item_info(item_id, config)
            if isinstance(info, str):
                return info
            add_to_cart.append(info)

        purchased = []
        for item_id in user["purchased"]:
            info = get_item_info(item_id, config)
            if isinstance(info, str):
                return info
            purchased.append(info)

        # --- Construct comparison prompt ---
        prompt = (
            " You are a sales assistant tasked with recommending products."
            " Consider the following"
            " <rules>"
            " 1. Recommend lower-priced items."
            f" 2. Take user age {user['age']}, gender {user['gender']} into account."
            f" 3. Reflect on historical visit product: {visted}."
            f" 4. Reflect on historical add-to-cart actions: {add_to_cart}."
            f" 5. Reflect on historical purchases: {purchased}."
            f" 6. Take user preferences into account: {preference}."
            f" 7. Available items: {items}."
            " 8. Output the recommended item in JSON format, preserving the original format."
            " 9. Sort by score in item."
            " <\\rules>"
        )

        summary = call_bedrock_llm(prompt, config)
        if isinstance(summary, str) and summary.startswith("Error generating summary:"):
            return summary

        result = {"items": items, "summarize": summary}
        return json.dumps(result)
    except Exception as exc:
        logger.error("Error comparing products: %s", exc)
        return f"Error comparing products: {exc}"
