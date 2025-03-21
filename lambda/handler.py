import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
import os
import base64
import io
from io import StringIO
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

def lambda_handler(event, context):
    print("Event Received:", event)
    api_path = event['apiPath']
    response_code = 200
    result = ''
    try:
        if api_path == '/searchProduct':
            condition = get_parameter(event, 'condition')
            result = search_product(condition)
        elif api_path == '/compareProduct':
            user_id = get_parameter(event, 'user_id')
            condition = get_parameter(event, 'condition')
            preference = get_parameter(event, 'preference')
            result = compare_product(user_id, condition, preference)
        elif api_path == '/getRecommendation':
            user_id = get_parameter(event, 'user_id')
            preference = get_parameter(event, 'preference')
            result = get_recommendation(user_id, preference)
        else:
            response_code = 404
            result = "Unrecognized API path: {}".format(api_path)
    except Exception as e:
        response_code = 404
        result = "An error occurred: {}".format(str(e))
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': event['actionGroup'],
            'apiPath': event['apiPath'],
            'httpMethod': event['httpMethod'],
            'httpStatusCode': response_code,
            'responseBody': {'application/json': {'body': result}}
        }
    }

def get_parameter(event, name):
    for param in event['parameters']:
        if param['name'] == name:
            return param['value']
    return None

def get_recommendation(user_id, preference):
    client = boto3.client('personalize-runtime')
    # TODO REAd from ENV. However, personalize runtime will be part of workshop
    # recommender_arn = 'arn:aws:personalize:us-east-1:xxx:recommender/recommended-for-you'
    recommender_arn = os.environ.get('RECOMMENDER_ARN', None)
    if recommender_arn is None:
        raise Exception("No recommender arn found")
    response = client.get_recommendations(
        recommenderArn=recommender_arn,
        userId=str(user_id),
        numResults=5
    )
    items = response.get('itemList', [])
    user = get_user_info(user_id)
    visted = []
    for item_id in user['visted']:
        visted.append(get_item_info(item_id))
    add_to_cart = []
    for item_id in user['add_to_cart']:
        add_to_cart.append(get_item_info(item_id))
    purchased = []
    for item_id in user['purchased']:
        purchased.append(get_item_info(item_id))
    prompt = f" You are a sales assistant tasked with recommending products. Consider the following\
        <rules>\
        1. Recommend lower-priced items.\
        2. Take user age {user['age']}, gender {user['gender']} into account.\
        3. Reflect on historical visit product: {visted}.\
        4. Reflect on historical add-to-cart actions: {add_to_cart}.\
        5. Reflect on historical purchases: {purchased}.\
        6. Take user preferences into account: {preference}.\
        7. Available items: {items}.\
        8. Output the recommended item in JSON format, preserving the original format.\
        9. Sort by score in item.\
        <\rules>"
    result = {
        'items': items,
        'summarize': call_bedrock(prompt)
    }
    return json.dumps(result)

def compare_product(user_id, condition, preference):
    items = search_product(condition)
    user = get_user_info(user_id)
    visted = []
    for item_id in user['visted']:
        visted.append(get_item_info(item_id))
    add_to_cart = []
    for item_id in user['add_to_cart']:
        add_to_cart.append(get_item_info(item_id))
    purchased = []
    for item_id in user['purchased']:
        purchased.append(get_item_info(item_id))
    prompt = f" You are a sales assistant tasked with recommending products. Consider the following\
        <rules>\
        1. Recommend lower-priced items.\
        2. Take user age {user['age']}, gender {user['gender']} into account.\
        3. Reflect on historical visit product: {visted}.\
        4. Reflect on historical add-to-cart actions: {add_to_cart}.\
        5. Reflect on historical purchases: {purchased}.\
        6. Take user preferences into account: {preference}.\
        7. Available items: {items}.\
        8. Output the recommended item in JSON format, preserving the original format.\
        9. Sort by score in item.\
        <\rules>"
    result = {
        'items': items,
        'summarize': call_bedrock(prompt)
    }
    return json.dumps(result)

def search_product(condition):
    # TODO Double check collection id is part of endpoint
    host = os.environ['AOSS_COLLECTION_ID']+'.'+os.environ['AOSS_REGION']+'.aoss.amazonaws.com'
    service = 'aoss'
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, os.environ['AOSS_REGION'], service)
    client = OpenSearch(
        hosts = [{'host': host, 'port': 443}],
        http_auth = auth,
        use_ssl = True,
        verify_certs = True,
        connection_class = RequestsHttpConnection,
        pool_maxsize = 20
    )
    text_embedding = get_embedding_for_text(condition)
    query = {
        "size": 5,
        "query": {
            "knn": {
                "multimodal_vector": {
                    "vector": text_embedding[0]['embedding'],
                    "k": 5
                }
            }
        },
        "_source": ["item_id", "price", "style", "image_product_description", "image_path"]
    }
    text_based_search_response = client.search(
        body=query,
        index="product-search-multimodal-index"
    )
    result = []
    hits = text_based_search_response['hits']['hits']
    for hit in hits:
        data = {
            "item_id": hit['_source']['item_id'],
            "score": hit['_score'],
            "image": hit['_source']['image_path'],
            "price": hit['_source']['price'],
            "style": hit['_source']['style'],
            "description": hit['_source']['image_product_description'],
        }
        result.append(data)
    return json.dumps(result)

def get_embedding_for_text(text):
    body = json.dumps(
        {
            "inputText": text
        }
    )
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
    response = bedrock_runtime.invoke_model(
        body=body,
        modelId="amazon.titan-embed-image-v1",
        accept="application/json",
        contentType="application/json"
    )
    vector_json = json.loads(response['body'].read().decode('utf8'))
    return vector_json, text

def call_bedrock(prompt, image_data = None):
    # TODO read from ENV?
    model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
    max_tokens = 1000
    # Create the text content
    text_content = {
        "type": "text",
        "text": prompt
    }
    # Create the image content if image_data is provided
    if image_data:
        image_content = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_data
            }
        }
        content = [image_content, text_content]
    else:
        content = [text_content]
    messages = [{
        "role": "user",
        "content": content
    }]
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages
        }
    )
    response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
    result = json.loads(response.get('body').read())['content'][0]['text']
    print(result)
    return result

def get_item_info(item_id):
    dynamodb = boto3.resource('dynamodb')
    # TODO Read from ENV
    table = dynamodb.Table('item_table')
    response = table.query(KeyConditionExpression=Key('ITEM_ID').eq(item_id))
    item = response['Items'][0]
    result = {
        "item_id": str(item['ITEM_ID']),
        "title": str(item['NAME']),
        "price": str(item['PRICE']),
        "style": str(item['STYLE']),
        "image": str(item['IMAGE'])
    }
    return result

def get_user_info(user_id):
    dynamodb = boto3.resource('dynamodb')
    # TODO Read from ENV
    table = dynamodb.Table('user_table')
    response = table.query(KeyConditionExpression=Key('USER_ID').eq(int(user_id)))
    item = response['Items'][0]
    # TODO where is visited, add_to_cart, purchased?
    result = {
        "user_id": str(item['USER_ID']),
        "age": str(item['AGE']),
        "gender": str(item['GENDER']),
        "visted": ['e1669081-8ffc-4dec-97a6-e9176d7f6651'],
        "add_to_cart": ['cfafd627-7d6b-43a5-be05-4c7937be417d'],
        "purchased": ['6e6ad102-7510-4a02-b8ce-5a0cd6f431d1']
    }
    return result
