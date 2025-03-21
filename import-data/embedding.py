import os
import json
import base64
import boto3
from botocore.config import Config
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
import argparse

# Add argument parser at the beginning
parser = argparse.ArgumentParser(description='Embedding')
parser.add_argument('--host', required=True, help='OpenSearch host domain')
parser.add_argument('--bucket', required=True, help='S3 bucket name')
args = parser.parse_args()
host = args.host
bucket_name = args.bucket

def get_embedding_for_product_image_and_description(image_path, description):
    """Fetch embedding for product image and description using Amazon Bedrock."""
    s3_response = s3_client.get_object(Bucket=bucket_name, Key=image_path)
    image_content = s3_response['Body'].read()
    image_base64 = base64.b64encode(image_content).decode('utf-8')

    request_body = json.dumps({
        "inputImage": image_base64,
        "inputText": description
    })
    response = bedrock.invoke_model(
        body=request_body,
        modelId="amazon.titan-embed-image-v1",
        accept="application/json",
        contentType="application/json"
    )
    return json.loads(response['body'].read().decode('utf8'))

# Setup AWS clients and resources
session = boto3.Session(region_name='us-east-1')
s3_client = session.client('s3', config=Config(retries={'max_attempts': 5, 'mode': 'standard'}))
dynamodb = session.resource('dynamodb', config=Config(retries={'max_attempts': 5, 'mode': 'standard'}))
table = dynamodb.Table('item_table')
bedrock = boto3.client(
    service_name="bedrock-runtime", region_name="us-east-1",
    endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com"
)

# Scan DynamoDB table to retrieve items
response = table.scan()
items = [item for item in response['Items']]

# Setup OpenSearch connection
aoss_client = boto3.client('opensearchserverless')
auth = AWSV4SignerAuth(session.get_credentials(), "us-east-1", 'aoss')
client = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

# Process each item to get embeddings and index in OpenSearch
for i, item in enumerate(items):
    try:
        # 檢查是否有描述
        if not item.get('DESCRIPTION'):
            print(f"Skipping item {i} (ID: {item.get('ITEM_ID')}) due to missing description.")
            continue

        vector_data = get_embedding_for_product_image_and_description(item.get('IMAGE'), item.get('DESCRIPTION'))
        
        embedding_request_body = {
            "item_id": item['ITEM_ID'],
            "image_path": item['IMAGE'],
            "image_product_description": item['DESCRIPTION'],
            "price": item.get('PRICE'),
            "style": item.get('STYLE'),
            "multimodal_vector": vector_data['embedding']
        }
        
        response = client.index(
            index="product-search-multimodal-index",
            body=embedding_request_body
        )
        print(f"Indexed item {i} (ID: {item['ITEM_ID']}): {response}")
    
    except Exception as e:
        print(f"Error processing item {i} (ID: {item.get('ITEM_ID')}): {str(e)}")
        continue  