"""Shared helper utilities for AgentCore Sales Agent tools.

Ported from lambda/handler.py with configurable table names, model IDs,
and try/except error handling returning descriptive messages.
"""

import json
import logging

import boto3
from boto3.dynamodb.conditions import Key
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

from config import Config

logger = logging.getLogger(__name__)


def get_user_info(user_id: int, config: Config) -> dict | str:
    """Fetch user profile from DynamoDB user_table.

    Args:
        user_id: The user identifier (will be cast to int for the query).
        config: Runtime configuration with table names.

    Returns:
        Dict with user_id, age, gender, visted, add_to_cart, purchased
        or a descriptive error string if the user is not found.
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(config.user_table_name)
        response = table.query(
            KeyConditionExpression=Key("USER_ID").eq(int(user_id))
        )
        if not response.get("Items"):
            return f"User {user_id} not found"
        item = response["Items"][0]
        return {
            "user_id": str(item["USER_ID"]),
            "age": str(item["AGE"]),
            "gender": str(item["GENDER"]),
            "visted": item.get("visted", []),
            "add_to_cart": item.get("add_to_cart", []),
            "purchased": item.get("purchased", []),
        }
    except Exception as exc:
        logger.error("Error fetching user %s: %s", user_id, exc)
        return f"Error fetching user {user_id}: {exc}"


def get_item_info(item_id: str, config: Config) -> dict | str:
    """Fetch item details from DynamoDB item_table.

    Args:
        item_id: The item identifier.
        config: Runtime configuration with table names.

    Returns:
        Dict with item_id, title, price, style, image
        or a descriptive error string if the item is not found.
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(config.item_table_name)
        response = table.query(
            KeyConditionExpression=Key("ITEM_ID").eq(item_id)
        )
        if not response.get("Items"):
            return f"Item {item_id} not found"
        item = response["Items"][0]
        return {
            "item_id": str(item["ITEM_ID"]),
            "title": str(item["NAME"]),
            "price": str(item["PRICE"]),
            "style": str(item["STYLE"]),
            "image": str(item["IMAGE"]),
        }
    except Exception as exc:
        logger.error("Error fetching item %s: %s", item_id, exc)
        return f"Error fetching item {item_id}: {exc}"


def get_embedding_for_text(text: str) -> list[float] | str:
    """Generate a vector embedding via Bedrock Titan Embed Image V1.

    Args:
        text: The input text to embed.

    Returns:
        List of floats representing the embedding vector,
        or a descriptive error string on failure.
    """
    try:
        body = json.dumps({"inputText": text})
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime", region_name="us-east-1"
        )
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId="amazon.titan-embed-image-v1",
            accept="application/json",
            contentType="application/json",
        )
        vector_json = json.loads(response["body"].read().decode("utf8"))
        return vector_json["embedding"]
    except Exception as exc:
        logger.error("Error generating embedding: %s", exc)
        return f"Error generating embedding: {exc}"


def call_bedrock_llm(prompt: str, config: Config) -> str:
    """Invoke Bedrock Claude with the given prompt.

    Args:
        prompt: The text prompt to send to the model.
        config: Runtime configuration with model_id.

    Returns:
        The text content from the model response,
        or a descriptive error string on failure.
    """
    try:
        max_tokens = 1000
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ]
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": messages,
            }
        )
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime", region_name="us-east-1"
        )
        response = bedrock_runtime.invoke_model(
            body=body, modelId=config.model_id
        )
        result = json.loads(response["body"].read())["content"][0]["text"]
        return result
    except Exception as exc:
        logger.error("Error generating summary: %s", exc)
        return f"Error generating summary: {exc}"


def create_opensearch_client(config: Config) -> OpenSearch | str:
    """Create an OpenSearch client authenticated with AWSV4SignerAuth for AOSS.

    Args:
        config: Runtime configuration with aoss_collection_id and aoss_region.

    Returns:
        An OpenSearch client instance,
        or a descriptive error string on failure.
    """
    try:
        host = (
            f"{config.aoss_collection_id}.{config.aoss_region}.aoss.amazonaws.com"
        )
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, config.aoss_region, "aoss")
        client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )
        return client
    except Exception as exc:
        logger.error("Error creating OpenSearch client: %s", exc)
        return f"Error creating OpenSearch client: {exc}"
