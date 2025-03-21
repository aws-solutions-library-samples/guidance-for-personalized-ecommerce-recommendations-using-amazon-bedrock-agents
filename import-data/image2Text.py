import boto3
import base64
import json
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from botocore.exceptions import ClientError
import argparse

def retry_with_exponential_backoff(func):
    def wrapper(*args, **kwargs):
        max_retries = 5
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                if e.response['Error']['Code'] in ['ThrottlingException', 'ProvisionedThroughputExceededException']:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise
    return wrapper

def create_aws_client(service_name, region='us-east-1'):
    config = Config(retries={'max_attempts': 5, 'mode': 'standard'})
    return boto3.client(service_name, region_name=region, config=config)

s3_client = create_aws_client('s3')
bedrock_runtime = create_aws_client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb', config=Config(retries={'max_attempts': 5, 'mode': 'standard'}))
table = dynamodb.Table('item_table')

@retry_with_exponential_backoff
def get_image_base64(bucket, key):
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return base64.b64encode(response['Body'].read()).decode('utf-8')
    except Exception as e:
        print(f"Error retrieving image {key} from bucket {bucket}: {str(e)}")
        raise

@retry_with_exponential_backoff
def call_bedrock(prompt, image_base64):
    model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    })
    response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
    return json.loads(response['body'].read())['content'][0]['text']

@retry_with_exponential_backoff
def insert_description_to_dynamodb(item_id, description):
    return table.update_item(
        Key={'ITEM_ID': item_id},
        UpdateExpression='SET DESCRIPTION = :desc',
        ExpressionAttributeValues={':desc': description},
        ReturnValues='UPDATED_NEW'
    )

def process_item(item, bucket_name):
    try:
        image_base64 = get_image_base64(bucket_name, item.get('IMAGE'))
        prompt = f"This is a {item['NAME']} photo, please write a description for this product."
        description = call_bedrock(prompt, image_base64)
        insert_description_to_dynamodb(item['ITEM_ID'], description)
        return f"Processed item {item['ITEM_ID']}."
    except Exception as e:
        return f"Failed to process item {item['ITEM_ID']}: {str(e)}"

def process_items(bucket_name):
    items = []
    last_evaluated_key = None

    while True:
        scan_kwargs = {'ExclusiveStartKey': last_evaluated_key} if last_evaluated_key else {}
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')
        
        if not last_evaluated_key:
            break

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_item = {executor.submit(process_item, item, bucket_name): item for item in items}
        for future in as_completed(future_to_item):
            print(future.result())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process items and generate descriptions.")
    parser.add_argument("bucket_name", help="The name of the S3 bucket containing the images.")
    
    args = parser.parse_args()
    
    process_items(args.bucket_name)