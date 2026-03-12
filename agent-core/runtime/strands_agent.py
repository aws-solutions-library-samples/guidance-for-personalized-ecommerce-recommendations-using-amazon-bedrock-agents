"""
Sales Agent — Strands SDK on Bedrock AgentCore Runtime
All tools native (no MCP round-trip). Optimized for <5s warm latency.
Configuration loaded from AWS Systems Manager Parameter Store.
"""
import os
import sys
import json
import logging
import time
from datetime import datetime
from functools import wraps
import boto3
from boto3.dynamodb.conditions import Key
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

# Configure logging first with DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)
logger.info("Starting Sales Agent Runtime...")
logger.debug(f"Python version: {sys.version}")
logger.debug(f"Working directory: {os.getcwd()}")

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

app = BedrockAgentCoreApp()

MCP_REGION = os.environ.get('MCP_REGION', 'us-east-1')

# ── OpenTelemetry Configuration ──
def configure_opentelemetry():
    """
    Configure OpenTelemetry SDK with AWS X-Ray exporter for traces
    and CloudWatch exporter for metrics.
    
    This function sets up:
    - TracerProvider with OTLP exporter for distributed tracing
    - MeterProvider with OTLP exporter for custom metrics
    - Service name and resource attributes
    """
    # Temporarily disabled - ADOT collector not configured
    logger.info("OpenTelemetry configuration skipped (ADOT collector not available)")
    return

# Initialize OpenTelemetry
try:
    configure_opentelemetry()
except Exception as e:
    logger.warning(f"Failed to configure OpenTelemetry: {e}")

# Get tracer and meter for instrumentation (no-op if OpenTelemetry not configured)
try:
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)
    
    # Create custom metrics
    tool_execution_duration = meter.create_histogram(
        name="tool.execution.duration",
        description="Duration of tool execution in seconds",
        unit="s",
    )
    
    agent_invocation_duration = meter.create_histogram(
        name="agent.invocation.duration",
        description="Duration of agent invocation in seconds",
        unit="s",
    )
except Exception as e:
    logger.warning(f"Failed to create metrics: {e}")
    # Create dummy objects that won't break the code
    class DummyMetric:
        def record(self, *args, **kwargs):
            pass
    tool_execution_duration = DummyMetric()
    agent_invocation_duration = DummyMetric()

# ── Configuration loading from Parameter Store ──
def load_config(stage: str = None) -> dict:
    """
    Load configuration from AWS Systems Manager Parameter Store.
    
    Args:
        stage: Deployment stage (e.g., 'dev', 'staging', 'prod')
               If not provided, attempts to read from STAGE environment variable
    
    Returns:
        Dictionary with configuration values
    
    Raises:
        SystemExit: If required parameters are missing
    """
    if stage is None:
        stage = os.environ.get('STAGE')
    
    if not stage:
        logger.error("STAGE environment variable not set. Cannot load configuration.")
        sys.exit(1)
    
    try:
        ssm = boto3.client('ssm', region_name=MCP_REGION)
        prefix = f'/sales-agent/{stage}/'
        
        logger.info(f"Loading configuration from Parameter Store: {prefix}")
        response = ssm.get_parameters_by_path(
            Path=prefix,
            Recursive=True,
            WithDecryption=True
        )
        
        if not response.get('Parameters'):
            logger.error(f"No parameters found at path: {prefix}")
            logger.error(f"Please ensure Parameter Store entries exist for stage '{stage}'")
            sys.exit(1)
        
        config = {}
        for param in response['Parameters']:
            key = param['Name'].replace(prefix, '')
            config[key] = param['Value']
            logger.info(f"Loaded parameter: {key}")
        
        # Validate required parameters
        required_params = ['item_table', 'user_table', 'aoss_endpoint', 'recommender_arn', 'memory_id']
        missing_params = [p for p in required_params if p not in config]
        
        if missing_params:
            logger.error(f"Missing required parameters: {', '.join(missing_params)}")
            logger.error(f"Required parameters: {', '.join(required_params)}")
            logger.error(f"Found parameters: {', '.join(config.keys())}")
            sys.exit(1)
        
        logger.info("Configuration loaded successfully")
        return config
        
    except Exception as e:
        logger.error(f"Failed to load configuration from Parameter Store: {e}")
        sys.exit(1)


# Load configuration at module level
_config = load_config()

# Extract configuration values
MEMORY_ID = _config['memory_id']
ITEM_TABLE = _config['item_table']
USER_TABLE = _config['user_table']
AOSS_ENDPOINT = _config['aoss_endpoint']
RECOMMENDER_ARN = _config['recommender_arn']

# ── Shared AWS clients (module-level, reused across invocations) ──
_bedrock_rt = boto3.client(service_name='bedrock-runtime', region_name=MCP_REGION)
_personalize_rt = boto3.client('personalize-runtime', region_name=MCP_REGION)
_dynamodb = boto3.resource('dynamodb', region_name=MCP_REGION)

# OpenSearch Serverless client setup
_aoss_host = AOSS_ENDPOINT.replace('https://', '').replace('http://', '')
_aoss_session = boto3.Session()
_aoss_auth = AWSV4SignerAuth(_aoss_session.get_credentials(), MCP_REGION, 'aoss')
_aoss_client = OpenSearch(
    hosts=[{'host': _aoss_host, 'port': 443}],
    http_auth=_aoss_auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20,
)

logger.info(f"Initialized AWS clients for region: {MCP_REGION}")
logger.info(f"Using DynamoDB tables: {ITEM_TABLE}, {USER_TABLE}")
logger.info(f"Using OpenSearch endpoint: {AOSS_ENDPOINT}")
logger.info(f"Using Personalize recommender: {RECOMMENDER_ARN}")
logger.info(f"Using AgentCore Memory: {MEMORY_ID}")

logger.debug("About to define helper functions...")

# ── Helper functions ──
def _get_item_info(item_id: str) -> dict:
    """
    Retrieve item information from DynamoDB.
    
    Args:
        item_id: Product item identifier
    
    Returns:
        Dictionary with item details (item_id, title, price, style)
    """
    try:
        resp = _dynamodb.Table(ITEM_TABLE).query(
            KeyConditionExpression=Key('ITEM_ID').eq(item_id)
        )
        if resp['Items']:
            it = resp['Items'][0]
            return {
                "item_id": str(it['ITEM_ID']),
                "title": str(it['NAME']),
                "price": str(it['PRICE']),
                "style": str(it['STYLE'])
            }
    except Exception as e:
        logger.warning(f"Failed to get item info for {item_id}: {e}")
    
    return {"item_id": item_id, "title": "Unknown", "price": "0", "style": "unknown"}


def _get_user_info(user_id: str) -> dict:
    """
    Retrieve user information from DynamoDB.
    
    Args:
        user_id: User identifier
    
    Returns:
        Dictionary with user details (user_id, age, gender, visited, add_to_cart, purchased)
    """
    try:
        resp = _dynamodb.Table(USER_TABLE).query(
            KeyConditionExpression=Key('USER_ID').eq(int(user_id))
        )
        if resp['Items']:
            it = resp['Items'][0]
            return {
                "user_id": str(it['USER_ID']),
                "age": str(it.get('AGE', '?')),
                "gender": str(it.get('GENDER', '?')),
                "visited": it.get('VISITED', []),
                "add_to_cart": it.get('ADD_TO_CART', []),
                "purchased": it.get('PURCHASED', [])
            }
    except Exception as e:
        logger.warning(f"Failed to get user info for {user_id}: {e}")
    
    return {
        "user_id": user_id,
        "age": "?",
        "gender": "?",
        "visited": [],
        "add_to_cart": [],
        "purchased": []
    }


# ── Native tools ──
@tool
def search_product(condition: str) -> str:
    """
    Search for products by text condition using vector similarity.
    
    Args:
        condition: Natural language product description
    
    Returns:
        JSON string with array of matching products
    """
    start_time = time.time()
    
    try:
        # Generate embedding using Bedrock Titan Embed model
        body = json.dumps({"inputText": condition})
        resp = _bedrock_rt.invoke_model(
            body=body,
            modelId="amazon.titan-embed-image-v1",
            accept="application/json",
            contentType="application/json",
        )
        vec = json.loads(resp['body'].read().decode('utf8'))['embedding']
        
        # Query OpenSearch Serverless with vector similarity
        hits = _aoss_client.search(
            body={
                "size": 3,
                "query": {
                    "knn": {
                        "multimodal_vector": {
                            "vector": vec,
                            "k": 3
                        }
                    }
                },
                "_source": ["item_id", "price", "style", "image_product_description"]
            },
            index="product-search-multimodal-index",
        )
        
        # Format results
        results = [{
            "item_id": h['_source']['item_id'],
            "price": h['_source']['price'],
            "style": h['_source']['style'],
            "desc": h['_source']['image_product_description'][:120],
        } for h in hits['hits']['hits']]
        
        duration = time.time() - start_time
        tool_execution_duration.record(duration, {"tool.name": "search_product", "status": "success"})
        
        logger.info(f"search_product found {len(results)} results for: {condition}")
        return json.dumps(results)
        
    except Exception as e:
        duration = time.time() - start_time
        tool_execution_duration.record(duration, {"tool.name": "search_product", "status": "error"})
        
        logger.error(f"search_product error: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_recommendation(user_id: str) -> str:
    """
    Get personalized product recommendations for a user.
    
    Args:
        user_id: User identifier for personalization
    
    Returns:
        JSON string with recommendations and summary
    """
    start_time = time.time()
    
    try:
        # Get recommendations from Personalize
        resp = _personalize_rt.get_recommendations(
            recommenderArn=RECOMMENDER_ARN,
            userId=str(user_id),
            numResults=5,
        )
        items = resp.get('itemList', [])
        
        # Get user history
        user = _get_user_info(user_id)
        visited = [_get_item_info(i) for i in user['visited'][:3]]
        add_to_cart = [_get_item_info(i) for i in user['add_to_cart'][:3]]
        purchased = [_get_item_info(i) for i in user['purchased'][:3]]
        
        # Generate summary using Bedrock
        prompt = (
            f"Recommend products. User age={user['age']}, gender={user['gender']}. "
            f"Visited: {visited}. Cart: {add_to_cart}. Purchased: {purchased}. "
            f"Preference: {preference}. Available: {items}. "
            "Output JSON array of recommended items sorted by score."
        )
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        })
        
        result = json.loads(
            _bedrock_rt.invoke_model(
                body=body,
                modelId="anthropic.claude-3-haiku-20240307-v1:0"
            )['body'].read()
        )['content'][0]['text']
        
        duration = time.time() - start_time
        tool_execution_duration.record(duration, {"tool.name": "get_recommendation", "status": "success"})
        
        logger.info(f"get_recommendation generated recommendations for user {user_id}")
        return json.dumps({"items": items, "summarize": result})
        
    except Exception as e:
        duration = time.time() - start_time
        tool_execution_duration.record(duration, {"tool.name": "get_recommendation", "status": "error"})
        
        logger.error(f"get_recommendation error: {e}")
        return json.dumps({"error": str(e)})


# ── Model configuration ──
_model = BedrockModel(
    model_id="us.amazon.nova-lite-v1:0",
    region_name=MCP_REGION,
    max_tokens=300,
)

SYSTEM_PROMPT = (
    "You are a concise sales assistant. "
    "When a customer asks to buy or find a product, IMMEDIATELY call search_product — do not ask clarifying questions first. "
    "Use get_recommendation when user_id and preference are provided. "
    "Always include item_id and price in your response. Respond in the customer's language. Be brief."
)

_all_tools = [search_product, get_recommendation]

logger.debug("Tools and model configured successfully")
logger.debug(f"About to define entrypoint decorator...")

# ── AgentCore entrypoint ──
@app.entrypoint
async def agent_invocation(payload):
    """
    Process agent invocation with streaming response.
    
    Args:
        payload: Dictionary with:
            - prompt: User message (required)
            - actor_id: User identifier (optional, default: "default-user")
            - session_id: Session identifier (optional, auto-generated)
    
    Yields:
        Event dictionaries with agent response chunks
    """
    start_time = time.time()
    
    user_message = payload.get("prompt", "No prompt provided.")
    actor_id = payload.get("actor_id", "default-user")
    session_id = payload.get("session_id", f"s-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    
    logger.info(f"Processing invocation - session: {session_id}, actor: {actor_id}")
    
    try:
        # Configure AgentCore Memory
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config={
                "/facts/{actorId}": RetrievalConfig(top_k=2, relevance_score=0.6)
            },
        )
        
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config,
            region_name=MCP_REGION,
        )
        
        # Create agent with tools and memory
        agent = Agent(
            model=_model,
            system_prompt=SYSTEM_PROMPT,
            tools=_all_tools,
            session_manager=session_manager,
        )
        
        # Stream response
        stream = agent.stream_async(user_message)
        event_count = 0
        async for event in stream:
            event_count += 1
            yield event
        
        duration = time.time() - start_time
        agent_invocation_duration.record(duration, {"status": "success"})
        
        logger.info(f"Completed invocation - session: {session_id}, duration: {duration:.2f}s")
        
    except Exception as e:
        duration = time.time() - start_time
        agent_invocation_duration.record(duration, {"status": "error"})
        
        logger.error(f"Agent invocation error: {e}")
        raise


logger.debug("Entrypoint function defined successfully")
logger.debug("Module initialization complete, about to check if __name__ == '__main__'")
logger.debug("Note: BedrockAgentCoreApp automatically provides /ping endpoint for health checks")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("STARTING BEDROCK AGENTCORE APP")
    logger.info("=" * 60)
    try:
        # BedrockAgentCore requires port 8080 per AWS documentation
        logger.info("Calling app.run() with host=0.0.0.0 and port=8080...")
        app.run(host="0.0.0.0", port=8080)
        logger.info("app.run() completed (this should not be reached)")
    except Exception as e:
        logger.error(f"FATAL ERROR starting app: {e}", exc_info=True)
        sys.exit(1)
