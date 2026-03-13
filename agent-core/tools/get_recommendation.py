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
def get_recommendation(user_id: str) -> str:
    """Get personalized product recommendations for a user.

    Args:
        user_id: The unique user identifier.

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
            results = []
            for i, item in enumerate(items, 1):
                info = get_item_info(item['itemId'], config)
                results.append(
                    f"{i}. {info['title']} (Item {info['item_id']}) - ${info['price']} - {info['style']}"
                )
            return "Recommendations:\n" + "\n".join(results) if results else "No recommendations found."
        except Exception as exc:
            logger.error("Recommendation service error: %s", exc)
            return f"Recommendation service unavailable: {exc}"

    except Exception as exc:
        logger.error("Error getting recommendations: %s", exc)
        return f"Error getting recommendations: {exc}"

