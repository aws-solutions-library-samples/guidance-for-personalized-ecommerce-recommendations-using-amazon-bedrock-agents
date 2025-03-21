import boto3
import os
import argparse
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Add argument parser at the beginning
parser = argparse.ArgumentParser(description='Create OpenSearch index')
parser.add_argument('--host', required=True, help='OpenSearch host domain')
args = parser.parse_args()

# Set up connection details
service = 'aoss'
region = 'us-east-1'
host = args.host
port = 443
credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, region, service)

# Establish client for OpenSearch
client = OpenSearch(
    hosts=[{'host': host, 'port': port}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    ssl_assert_hostname=False,
    ssl_show_warn=False,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

# Define the index configuration
index_name = "product-search-multimodal-index"
index_body = {
    "settings": {
        "index": {
            "number_of_shards": 2,
            "knn.algo_param": {"ef_search": 512},
            "knn": True
        }
    },
    "mappings": {
        "properties": {
            "item_id": {"type": "text"},
            "image_path": {"type": "text"},
            "image_product_description": {"type": "text"},
            "price": {"type": "text"},
            "style": {"type": "text"},
            "multimodal_vector": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "engine": "nmslib",
                    "space_type": "cosinesimil",
                    "name": "hnsw",
                    "parameters": {"ef_construction": 512, "m": 16}
                }
            }
        }
    }
}

# Check if the index exists and delete it if it does
if client.indices.exists(index=index_name):
    response = client.indices.delete(index=index_name)
    print(response)

# Create the index with the defined settings and mappings
response = client.indices.create(index=index_name, body=index_body)
print(response)
