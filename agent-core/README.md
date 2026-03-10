# AgentCore Sales Agent

A conversational sales assistant built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) and deployed on [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html). The agent provides three capabilities:

- **Product Search** — vector similarity search against OpenSearch Serverless using Titan embeddings
- **Product Comparison** — compares products using user profile, purchase history, and preferences via Bedrock Claude
- **Personalized Recommendations** — retrieves recommendations from Amazon Personalize enriched with user context

The agent is packaged as an ARM64 Docker image, deployed via a CDK stack that provisions ECR, CodeBuild, SSM Parameter Store, and a `CfnRuntime` resource.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager |
| [Docker](https://docs.docker.com/get-docker/) | latest | For container builds |
| [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | v2 | Configured with credentials |
| [AWS CDK v2](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) | ≥ 2.220.0 | Required for `aws_bedrockagentcore` module |

You also need an AWS account with access to:
- Amazon Bedrock (Claude and Titan Embed Image models)
- Amazon OpenSearch Serverless
- Amazon DynamoDB
- Amazon Personalize (optional, for recommendations)

## Setup

```bash
cd agent-core
uv sync
cp .env.example .env
# Edit .env with your values (see Environment Variables below)
```

## Local Development

Start the agent locally with the AgentCore dev server:

```bash
agentcore dev
```

Invoke the agent with a test prompt:

```bash
agentcore invoke --dev '{"prompt": "search for red shoes"}'
```

## Deployment

The `deploy.sh` script wraps `cdk deploy` to provision the full stack in a single command.

```bash
chmod +x deploy.sh
./deploy.sh --aoss-endpoint <collection-id> \
  --item-table item_table \
  --user-table user_table \
  --recommender-arn <arn> \
  --network-mode PUBLIC \
  --region us-east-1
```

### CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--aoss-endpoint` | Yes | — | OpenSearch Serverless collection ID |
| `--item-table` | No | `item_table` | DynamoDB item table name |
| `--user-table` | No | `user_table` | DynamoDB user table name |
| `--recommender-arn` | No | — | Amazon Personalize recommender ARN |
| `--network-mode` | No | `PUBLIC` | `PUBLIC` or `PRIVATE` |
| `--subnets` | If PRIVATE | — | Comma-separated subnet IDs |
| `--security-groups` | If PRIVATE | — | Comma-separated security group IDs |
| `--region` | No | — | AWS region for deployment |

On success the script prints the Runtime ARN, ECR URI, and a test invoke command.

## Updating the Runtime

After the initial deployment, `CfnRuntime` is created with the `:latest` image tag. When you rebuild and push a new image to ECR (e.g., via a subsequent `cdk deploy` or manual CodeBuild trigger), you need to tell AgentCore to pick up the new image:

```bash
# Via AWS CLI
aws bedrock-agent-runtime update-agent-runtime \
  --agent-runtime-arn <runtime-arn>
```

The **DEFAULT** endpoint automatically points to the latest version once the update completes. No additional routing changes are needed.

## Chat CLI

Interactively chat with the deployed agent:

```bash
python chat_cli.py --endpoint <url> --user-id <id>
```

- `--endpoint` — AgentCore Runtime agent endpoint URL (falls back to `AGENTCORE_ENDPOINT` env var)
- `--user-id` — optional user ID for personalized interactions

Type `exit` or `quit` to end the session.

## Running Tests

```bash
uv run pytest
```

Tests use Hypothesis for property-based testing and pytest with mocked AWS services.

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AOSS_COLLECTION_ID` | Yes | — | OpenSearch Serverless collection ID |
| `AOSS_REGION` | Yes | — | AWS region for AOSS |
| `RECOMMENDER_ARN` | No | — | Amazon Personalize recommender ARN |
| `ITEM_TABLE_NAME` | No | `item_table` | DynamoDB item table name |
| `USER_TABLE_NAME` | No | `user_table` | DynamoDB user table name |
| `MODEL_ID` | No | `anthropic.claude-sonnet-4-20250514` | Bedrock model ID |
| `PARAMETER_STORE_PREFIX` | No | `/agentcore/sales-agent/` | SSM parameter path prefix |
| `AGENTCORE_ENDPOINT` | No | — | Agent endpoint URL (used by `chat_cli.py`) |

At startup the agent reads configuration from AWS Systems Manager Parameter Store first, then falls back to environment variables for any missing values.
