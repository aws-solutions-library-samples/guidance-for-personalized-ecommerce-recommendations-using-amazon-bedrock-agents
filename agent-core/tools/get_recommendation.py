"""Personalized recommendation tool with user profile enrichment and LLM summary.

Ported from lambda/handler.py get_recommendation() to use Strands @tool decorator
with shared helpers for DynamoDB lookups and Bedrock LLM calls.
"""

import json
import logging

import boto3
from strands import tool

from config import Config
from tools.helpers import (
    call_bedrock_llm,
    get_item_info,
    get_user_info,
)

logger = logging.getLogger(__name__)

config = Config.load()


@tool
def get_recommendation(user_id: str, preference: str) -> str:
    """Get personalized product recommendations for a user.

    Args:
        user_id: The unique user identifier.
        preference: User's preferences to guide recommendations.

    Returns:
        JSON with 'items' list and 'summarize' recommendation text.
    """
    try:
        # --- Check recommender ARN ---
        if config.recommender_arn is None:
            return "Recommender is not configured. Set RECOMMENDER_ARN."

        # --- Get recommendations from Personalize ---
        try:
            client = boto3.client("personalize-runtime")
            response = client.get_recommendations(
                recommenderArn=config.recommender_arn,
                userId=str(user_id),
                numResults=5,
            )
            items = response.get("itemList", [])
        except Exception as exc:
            logger.error("Recommendation service error: %s", exc)
            return f"Recommendation service unavailable: {exc}"

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

        # --- Construct recommendation prompt ---
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
        logger.error("Error getting recommendations: %s", exc)
        return f"Error getting recommendations: {exc}"
