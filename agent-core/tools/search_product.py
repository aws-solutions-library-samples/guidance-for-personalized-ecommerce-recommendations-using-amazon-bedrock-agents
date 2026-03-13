"""Product search tool using OpenSearch Serverless vector search.

Ported from lambda/handler.py search_product() to use Strands @tool decorator
with shared helpers for embedding generation and OpenSearch client creation.
"""

import json
import logging

from strands import tool

from config import Config
from tools.helpers import create_opensearch_client, get_embedding_for_text

logger = logging.getLogger(__name__)

config = Config.load()

@tool
def search_product(condition: str) -> str:
    """Search for products based on a text condition describing customer requirements.

    Args:
        condition: Text description of what the customer is looking for.

    Returns:
        string with up to 5 matching products (item_id, score, image, price, style, description).
    """
    try:
        # Generate embedding for the search condition
        text_embedding = get_embedding_for_text(condition)
        if isinstance(text_embedding, str):
            return text_embedding

        # Create OpenSearch client
        client = create_opensearch_client(config)
        if isinstance(client, str):
            return client

        # Execute KNN query
        query = {
            "size": 3,
            "query": {
                "knn": {
                    "multimodal_vector": {
                        "vector": text_embedding,
                        "k": 3,
                    }
                }
            },
            "_source": [
                "item_id",
                "price",
                "style",
                "image_product_description",
            ],
        }

        response = client.search(
            body=query, index="product-search-multimodal-index"
        )

        # Map hits to product dicts
        result = []
        for hit in response["hits"]["hits"]:
            data = {
                "item_id": hit["_source"]["item_id"],
                "price": hit["_source"]["price"],
                "style": hit["_source"]["style"],
                "description": hit["_source"]["image_product_description"],
            }
            result.append(data)

        return json.dumps(result)
    except Exception as exc:
        logger.error("Error searching products: %s", exc)
        return f"Error searching products: {exc}"

