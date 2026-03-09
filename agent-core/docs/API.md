# API Documentation

This document provides comprehensive API documentation for the AgentCore CDK Infrastructure project, including runtime invocation payloads, tool interfaces, CLI commands, and Parameter Store schema.

## Table of Contents

- [Runtime Invocation API](#runtime-invocation-api)
- [Native Tools API](#native-tools-api)
- [CLI Command Reference](#cli-command-reference)
- [Parameter Store Schema](#parameter-store-schema)
- [CloudFormation Stack Outputs](#cloudformation-stack-outputs)

## Runtime Invocation API

### Agent Invocation Endpoint

The runtime exposes an agent invocation endpoint that processes user messages and returns streaming responses.

**Entrypoint**: `agent_invocation`

**Decorator**: `@app.entrypoint`

**Method**: Async generator function

### Request Payload

```python
{
    "prompt": str,           # Required: User message/query
    "actor_id": str,         # Optional: User identifier (default: "default-user")
    "session_id": str        # Optional: Session identifier (auto-generated if not provided)
}
```

**Field Descriptions**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | Yes | - | The user's message or query to the agent |
| `actor_id` | string | No | `"default-user"` | Unique identifier for the user/actor |
| `session_id` | string | No | Auto-generated | Session identifier for conversation continuity |

**Example Request**:
```json
{
    "prompt": "Find me a blue dress under $100",
    "actor_id": "user-12345",
    "session_id": "session-abc-2024-01-15"
}
```

### Response Format

The runtime returns an async iterator that yields event dictionaries with streaming response chunks.

**Response Events**:

```python
AsyncIterator[dict]
```

**Event Types**:

1. **Text Chunk Event**:
```json
{
    "type": "text",
    "content": "Here are some blue dresses I found..."
}
```

2. **Tool Invocation Event**:
```json
{
    "type": "tool_use",
    "tool_name": "search_product",
    "tool_input": {
        "condition": "blue dress under $100"
    }
}
```

3. **Tool Result Event**:
```json
{
    "type": "tool_result",
    "tool_name": "search_product",
    "result": "[{\"item_id\": \"123\", \"price\": \"$89.99\", ...}]"
}
```

4. **Completion Event**:
```json
{
    "type": "complete",
    "stop_reason": "end_turn"
}
```

### Error Responses

**Configuration Error**:
```json
{
    "type": "error",
    "error": "ConfigurationError",
    "message": "Missing required parameter: item_table",
    "details": "Check Parameter Store at /sales-agent/{stage}/item_table"
}
```

**Service Error**:
```json
{
    "type": "error",
    "error": "ServiceError",
    "message": "Failed to query DynamoDB",
    "details": "AccessDeniedException: User is not authorized to perform: dynamodb:Query"
}
```

### Session Management

**Session ID Generation**:
- If not provided, auto-generated with format: `s-{timestamp}`
- Example: `s-20240115143000`

**Session Persistence**:
- Sessions are stored in AgentCore Memory
- 30-day retention policy
- Retrieved automatically on subsequent invocations with same session_id

**Actor ID**:
- Used for user-specific memory retrieval
- Facts stored under `/facts/{actorId}` path
- Enables personalized context across sessions

## Native Tools API

### search_product Tool

Search for products using natural language descriptions with vector similarity search.

**Function Signature**:
```python
@tool
def search_product(condition: str) -> str:
    """
    Search for products by text condition using vector similarity.
    
    Args:
        condition: Natural language product description
    
    Returns:
        JSON string with array of matching products
    """
```

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `condition` | string | Yes | Natural language description of desired product |

**Input Examples**:
```python
"blue dress"
"casual summer shoes size 9"
"red leather handbag under $200"
"winter coat waterproof"
```

**Output Format**:
```json
[
    {
        "item_id": "ITEM-12345",
        "price": "$89.99",
        "style": "Casual Blue Dress",
        "desc": "Elegant blue dress perfect for summer occasions"
    },
    {
        "item_id": "ITEM-67890",
        "price": "$75.50",
        "style": "Blue Maxi Dress",
        "desc": "Comfortable maxi dress in navy blue"
    }
]
```

**Output Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | string | Unique product identifier |
| `price` | string | Product price with currency symbol |
| `style` | string | Product style/name |
| `desc` | string | Product description |

**Error Response**:
```json
{
    "error": "SearchError",
    "message": "Failed to generate embeddings",
    "details": "Bedrock service unavailable"
}
```

**Implementation Details**:
1. Generates embedding using Bedrock Titan Embed Image v1 model
2. Performs k-NN vector similarity search in OpenSearch Serverless
3. Retrieves top 5 matching products
4. Queries DynamoDB for full product details
5. Returns JSON array of products

**Performance**:
- Typical latency: 500-1500ms
- Depends on: embedding generation, vector search, DynamoDB queries

### get_recommendation Tool

Get personalized product recommendations based on user history and preferences.

**Function Signature**:
```python
@tool
def get_recommendation(user_id: str, preference: str) -> str:
    """
    Get personalized product recommendations.
    
    Args:
        user_id: User identifier for personalization
        preference: User's stated preference or requirement
    
    Returns:
        JSON string with recommendations and summary
    """
```

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | Unique user identifier |
| `preference` | string | Yes | User's preference or requirement |

**Input Examples**:
```python
user_id="user-12345", preference="casual wear"
user_id="user-67890", preference="formal occasions"
user_id="user-11111", preference="outdoor activities"
```

**Output Format**:
```json
{
    "items": [
        {
            "itemId": "ITEM-12345",
            "score": 0.95,
            "price": "$89.99",
            "style": "Casual Blue Shirt",
            "desc": "Comfortable cotton shirt for everyday wear"
        },
        {
            "itemId": "ITEM-67890",
            "score": 0.87,
            "price": "$65.00",
            "style": "Casual Jeans",
            "desc": "Classic fit denim jeans"
        }
    ],
    "summarize": "Based on your preference for casual wear, I recommend these comfortable and stylish items. The blue shirt pairs well with the classic jeans for a relaxed everyday look."
}
```

**Output Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `items` | array | Array of recommended products |
| `items[].itemId` | string | Product identifier |
| `items[].score` | number | Recommendation confidence score (0-1) |
| `items[].price` | string | Product price |
| `items[].style` | string | Product style/name |
| `items[].desc` | string | Product description |
| `summarize` | string | Natural language summary of recommendations |

**Error Response**:
```json
{
    "error": "RecommendationError",
    "message": "User not found in Personalize",
    "details": "No interaction data for user_id: user-12345"
}
```

**Implementation Details**:
1. Calls Amazon Personalize GetRecommendations API
2. Retrieves top recommended item IDs with scores
3. Queries DynamoDB for product details
4. Generates natural language summary using Bedrock (Claude or Nova)
5. Returns JSON with items and summary

**Performance**:
- Typical latency: 800-2000ms
- Depends on: Personalize API, DynamoDB queries, LLM inference

## CLI Command Reference

### Global Options

All CLI commands require the `--stage` parameter.

```bash
python cli/sales_agent_cli.py --stage STAGE COMMAND [OPTIONS]
```

**Global Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--stage` | Yes | Stage name (dev, staging, prod, or custom) |

### Parameter Management Commands

#### param set

Set a Parameter Store value.

**Usage**:
```bash
python cli/sales_agent_cli.py --stage STAGE param set --key KEY --value VALUE
```

**Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--key` | Yes | Parameter key name |
| `--value` | Yes | Parameter value |

**Examples**:
```bash
# Set DynamoDB table name
python cli/sales_agent_cli.py --stage dev param set --key item_table --value products-catalog

# Set OpenSearch endpoint
python cli/sales_agent_cli.py --stage dev param set --key aoss_endpoint --value https://xxxxx.us-east-1.aoss.amazonaws.com
```

**Output**:
```
✓ Parameter set: /sales-agent/dev/item_table = products-catalog
```

#### param get

Get a Parameter Store value.

**Usage**:
```bash
python cli/sales_agent_cli.py --stage STAGE param get --key KEY
```

**Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--key` | Yes | Parameter key name |

**Examples**:
```bash
python cli/sales_agent_cli.py --stage dev param get --key item_table
```

**Output**:
```
item_table: products-catalog
```

#### param list

List all Parameter Store entries for a stage.

**Usage**:
```bash
python cli/sales_agent_cli.py --stage STAGE param list
```

**Examples**:
```bash
python cli/sales_agent_cli.py --stage dev param list
```

**Output**:
```
Parameters for stage: dev
  item_table: products-catalog
  user_table: user-profiles
  aoss_endpoint: https://xxxxx.us-east-1.aoss.amazonaws.com
  recommender_arn: arn:aws:personalize:us-east-1:123456789012:recommender/my-rec
  s3_bucket: product-images-bucket
  memory_id: mem-abc123
```

### Runtime Invocation Commands

#### invoke

Invoke the runtime with a message.

**Usage**:
```bash
python cli/sales_agent_cli.py --stage STAGE invoke --message MESSAGE [--session-id SESSION_ID] [--actor-id ACTOR_ID]
```

**Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--message` | Yes | User message/query |
| `--session-id` | No | Session identifier for continuity |
| `--actor-id` | No | User identifier (default: "default-user") |

**Examples**:
```bash
# Simple invocation
python cli/sales_agent_cli.py --stage dev invoke --message "Find me a blue dress"

# With session and actor
python cli/sales_agent_cli.py --stage dev invoke \
  --message "Show me recommendations" \
  --session-id session-123 \
  --actor-id user-456
```

**Output** (streaming):
```
Agent: Let me search for blue dresses for you...

[Tool: search_product]
Input: {"condition": "blue dress"}

[Tool Result]
Found 5 matching products

Agent: Here are some beautiful blue dresses I found:

1. Elegant Blue Dress - $89.99
   Perfect for summer occasions

2. Blue Maxi Dress - $75.50
   Comfortable navy blue maxi dress

Would you like more details on any of these?
```

### Log Management Commands

#### logs

Retrieve runtime logs from CloudWatch.

**Usage**:
```bash
python cli/sales_agent_cli.py --stage STAGE logs [--tail N] [--start TIMESTAMP] [--end TIMESTAMP]
```

**Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--tail` | No | Number of recent log lines to retrieve |
| `--start` | No | Start timestamp (format: "YYYY-MM-DD HH:MM") |
| `--end` | No | End timestamp (format: "YYYY-MM-DD HH:MM") |

**Examples**:
```bash
# Get last 50 log lines
python cli/sales_agent_cli.py --stage dev logs --tail 50

# Get logs for time range
python cli/sales_agent_cli.py --stage dev logs \
  --start "2024-01-15 10:00" \
  --end "2024-01-15 11:00"
```

**Output**:
```
[2024-01-15T10:15:23.456Z] INFO: Agent invocation started
[2024-01-15T10:15:23.789Z] INFO: Loading configuration from Parameter Store
[2024-01-15T10:15:24.123Z] INFO: Tool invoked: search_product
[2024-01-15T10:15:25.456Z] INFO: OpenSearch query completed: 5 results
[2024-01-15T10:15:25.789Z] INFO: Agent invocation completed
```

### Status Commands

#### status

Display runtime deployment status.

**Usage**:
```bash
python cli/sales_agent_cli.py --stage STAGE status
```

**Examples**:
```bash
python cli/sales_agent_cli.py --stage dev status
```

**Output**:
```
Runtime Status for stage: dev

Stage: dev
Status: ACTIVE
Health: HEALTHY
Version: abc1234
Last Deployment: 2024-01-15 14:30:00 UTC
Endpoint: https://xxxxx.execute-api.us-east-1.amazonaws.com

CloudFormation Stack: SalesAgentRuntimeStack-dev
Stack Status: UPDATE_COMPLETE
```

### Help Commands

Get help for any command:

```bash
# Global help
python cli/sales_agent_cli.py --help

# Command-specific help
python cli/sales_agent_cli.py param --help
python cli/sales_agent_cli.py invoke --help
python cli/sales_agent_cli.py logs --help
python cli/sales_agent_cli.py status --help
```

## Parameter Store Schema

### Hierarchical Structure

All parameters use hierarchical naming with stage prefix:

```
/sales-agent/{stage}/{key}
```

**Example Paths**:
```
/sales-agent/dev/item_table
/sales-agent/dev/user_table
/sales-agent/staging/aoss_endpoint
/sales-agent/prod/recommender_arn
```

### Required Parameters

| Key | Type | Description | Example Value |
|-----|------|-------------|---------------|
| `item_table` | String | DynamoDB table name for product catalog | `products-catalog` |
| `user_table` | String | DynamoDB table name for user profiles | `user-profiles` |
| `aoss_endpoint` | String | OpenSearch Serverless collection endpoint | `https://xxxxx.us-east-1.aoss.amazonaws.com` |
| `recommender_arn` | String | Amazon Personalize recommender ARN | `arn:aws:personalize:us-east-1:123456789012:recommender/my-rec` |
| `s3_bucket` | String | S3 bucket name for product images | `product-images-bucket` |
| `memory_id` | String | AgentCore Memory resource ID (auto-created) | `mem-abc123xyz` |

### Parameter Types

**String Parameters**:
- `item_table`
- `user_table`
- `s3_bucket`

**SecureString Parameters** (encrypted):
- `aoss_endpoint`
- `recommender_arn`
- `memory_id`

### Parameter Tags

All parameters are tagged with:

| Tag Key | Tag Value | Description |
|---------|-----------|-------------|
| `Stage` | `{stage}` | Stage identifier |
| `ManagedBy` | `CDK` | Managed by AWS CDK |

### Parameter Tier

All parameters use **Standard** tier:
- Maximum value size: 4 KB
- No additional charges
- Suitable for configuration values

### Access Control

**IAM Policy for Runtime**:
```json
{
    "Effect": "Allow",
    "Action": [
        "ssm:GetParameter",
        "ssm:GetParametersByPath"
    ],
    "Resource": "arn:aws:ssm:*:*:parameter/sales-agent/*"
}
```

**IAM Policy for CLI**:
```json
{
    "Effect": "Allow",
    "Action": [
        "ssm:GetParameter",
        "ssm:GetParametersByPath",
        "ssm:PutParameter"
    ],
    "Resource": "arn:aws:ssm:*:*:parameter/sales-agent/*"
}
```

## CloudFormation Stack Outputs

### Stack Output Schema

After deployment, the CloudFormation stack exports these outputs:

| Output Key | Description | Example Value |
|------------|-------------|---------------|
| `VpcId` | VPC identifier | `vpc-0123456789abcdef0` |
| `RuntimeEndpoint` | Runtime invocation endpoint | `https://xxxxx.execute-api.us-east-1.amazonaws.com` |
| `CodeCommitRepositoryUrl` | Git repository clone URL | `https://git-codecommit.us-east-1.amazonaws.com/v1/repos/sales-agent-dev` |
| `ParameterStorePrefix` | Base path for parameters | `/sales-agent/dev/` |
| `LogGroupName` | CloudWatch log group name | `/aws/sales-agent/dev` |
| `EcrRepositoryUri` | ECR repository URI | `123456789012.dkr.ecr.us-east-1.amazonaws.com/sales-agent-dev` |

### Retrieving Stack Outputs

**Using AWS CLI**:
```bash
aws cloudformation describe-stacks \
  --stack-name SalesAgentRuntimeStack-dev \
  --query 'Stacks[0].Outputs' \
  --output table
```

**Using CDK CLI**:
```bash
cdk deploy --outputs-file outputs.json
cat outputs.json
```

**Using CLI Tool**:
```bash
python cli/sales_agent_cli.py --stage dev status
```

### Output Format

**JSON Format**:
```json
{
    "SalesAgentRuntimeStack-dev": {
        "VpcId": "vpc-0123456789abcdef0",
        "RuntimeEndpoint": "https://xxxxx.execute-api.us-east-1.amazonaws.com",
        "CodeCommitRepositoryUrl": "https://git-codecommit.us-east-1.amazonaws.com/v1/repos/sales-agent-dev",
        "ParameterStorePrefix": "/sales-agent/dev/",
        "LogGroupName": "/aws/sales-agent/dev",
        "EcrRepositoryUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/sales-agent-dev"
    }
}
```

## Error Codes and Handling

### Common Error Codes

| Error Code | Description | Resolution |
|------------|-------------|------------|
| `ConfigurationError` | Missing or invalid configuration | Check Parameter Store values |
| `ServiceError` | AWS service API error | Check IAM permissions and service quotas |
| `ValidationError` | Invalid input parameters | Verify input format and values |
| `AuthenticationError` | AWS credentials invalid | Configure AWS credentials |
| `ResourceNotFoundError` | Resource doesn't exist | Verify resource ARNs and names |

### Error Response Format

```json
{
    "error": "ErrorCode",
    "message": "Human-readable error message",
    "details": "Additional context and troubleshooting information",
    "timestamp": "2024-01-15T10:15:23.456Z"
}
```

### Troubleshooting Steps

1. **Check CloudWatch Logs**: `python cli/sales_agent_cli.py --stage dev logs --tail 100`
2. **Verify Parameters**: `python cli/sales_agent_cli.py --stage dev param list`
3. **Check IAM Permissions**: Review runtime execution role policies
4. **Verify Resources**: Ensure DynamoDB tables, OpenSearch collections exist
5. **Test Connectivity**: Verify VPC configuration and security groups

## API Versioning

**Current Version**: v1.0.0

**Compatibility**:
- Runtime API: Stable
- Tool interfaces: Stable
- CLI commands: Stable
- Parameter Store schema: Stable

**Breaking Changes**:
- Will be communicated via release notes
- Major version bump for breaking changes
- Backward compatibility maintained within major versions

## Rate Limits and Quotas

### Runtime Invocation

- **Concurrent invocations**: Limited by compute service (ECS/Fargate/App Runner)
- **Request timeout**: 300 seconds (5 minutes)
- **Payload size**: 256 KB maximum

### Tool Execution

- **search_product**: Limited by OpenSearch query rate
- **get_recommendation**: Limited by Personalize API rate (25 TPS default)

### Parameter Store

- **GetParameter**: 1000 TPS per account per region
- **PutParameter**: 100 TPS per account per region

### CloudWatch Logs

- **PutLogEvents**: 5 requests per second per log stream
- **Log retention**: 30 days

## Security Considerations

### Authentication

- **Runtime**: IAM role-based authentication
- **CLI**: AWS credentials (access key or IAM role)
- **Parameter Store**: IAM policy-based access control

### Encryption

- **In Transit**: TLS 1.2+ for all API calls
- **At Rest**: 
  - Parameter Store: AWS KMS encryption
  - CloudWatch Logs: Server-side encryption
  - ECR: AES-256 encryption

### Network Security

- **Runtime**: Deployed in private subnets
- **VPC Endpoints**: Private connectivity to AWS services
- **Security Groups**: Least-privilege inbound/outbound rules

---

## Additional Resources

- [README.md](../README.md) - Getting started guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture diagrams
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
