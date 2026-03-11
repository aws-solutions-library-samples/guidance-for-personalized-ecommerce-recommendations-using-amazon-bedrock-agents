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
cd agentcore-runtime
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

### Deploy Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--aoss-endpoint` | Yes | — | OpenSearch Serverless collection ID |
| `--item-table` | No | `item_table` | DynamoDB item table name |
| `--user-table` | No | `user_table` | DynamoDB user table name |
| `--recommender-arn` | No | — | Amazon Personalize recommender ARN |
| `--model-id` | No | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Bedrock model/inference profile ID |
| `--network-mode` | No | `PUBLIC` | `PUBLIC` or `PRIVATE` |
| `--subnets` | If PRIVATE | — | Comma-separated subnet IDs |
| `--security-groups` | If PRIVATE | — | Comma-separated security group IDs |
| `--aoss-data-policy-name` | No | — | AOSS data access policy name (auto-adds execution role) |
| `--region` | No | — | AWS region for deployment |

On success the script prints the Runtime ARN, ECR URI, and a test invoke command.

> **⚠️ OpenSearch Serverless Access**: When deploying a new environment, the execution role must be added to the AOSS data access policy or the agent will fail to query the product search index. Pass `--aoss-data-policy-name <policy-name>` to automate this. Without it, you must manually add the role ARN to the AOSS data access policy via the AWS console or CLI.

## Updating the Runtime

After the initial deployment, `CfnRuntime` is created with the `:latest` image tag. There are two ways to update the runtime when you change code.

### Option 1: Quick update via `update.sh` (recommended)

The `update.sh` script uploads your source to S3, triggers CodeBuild, waits for the build, and optionally updates the AgentCore Runtime hosting — all without a full `cdk deploy`.

```bash
# Build and update hosting automatically
./update.sh --stack-name AgentCoreStack-rc3 --auto-update-hosting --region us-east-1 --profile ray-testing

# Build only (reminds you to update hosting manually)
./update.sh --stack-name AgentCoreStack-rc3 --region us-east-1 --profile ray-testing
```

### Option 2: Full CDK re-deploy

Re-running `deploy.sh` re-packages source, triggers CodeBuild, and updates all infrastructure. Use this when you need to change SSM parameters, IAM roles, or other stack resources — not just the container image.

```bash
./deploy.sh --aoss-endpoint <collection-id> --env rc3 --region us-east-1 --profile ray-testing
```

### Option 3: Manual ECR push (fastest iteration)

For the quickest dev cycles, build and push the Docker image directly:

```bash
# Get your ECR URI from cdk-outputs.json
ECR_URI=$(python3 -c "import json; d=json.load(open('cdk-outputs-production.json')); print(d['AgentCoreStack-production']['EcrRepositoryUri'])")

# Authenticate with ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin "$ECR_URI"

# Build and push (from agentcore-runtime/)
docker build -t "$ECR_URI:latest" .
docker push "$ECR_URI:latest"

# Tell AgentCore to pick up the new image
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id <runtime-id>
```

The runtime ID is available in `cdk-outputs.json` under the `RuntimeId` key.

> **Note**: Pushing a new image with the same `:latest` tag does NOT automatically update the running AgentCore Runtime. You must call `update-agent-runtime` to trigger a new version deployment. The DEFAULT endpoint automatically points to the latest version once the update completes.

## Sales Agent CLI

A Click-based CLI for interacting with the deployed AgentCore Sales Agent. Supports invoking the agent, interactive chat, parameter management, log viewing, and deployment status checks.

### Installation

Dependencies are included in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Usage

```bash
python -m cli --stack-name <stack-name> [command]
```

The `--stack-name` option can also be set via the `AGENTCORE_STACK_NAME` environment variable.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `invoke -m "message"` | Send a single message | `python -m cli invoke -m "search for red shoes"` |
| `chat` | Interactive REPL session | `python -m cli chat` |
| `param set\|get\|list` | Manage Parameter Store values | `python -m cli param list` |
| `logs --tail N --start "1h ago"` | View CloudWatch logs | `python -m cli logs --tail 50` |
| `status` | Deployment status and ECS health | `python -m cli status` |
| `version` | Show CLI version | `python -m cli version` |

### Global Options

| Option | Description |
|--------|-------------|
| `--stack-name` | CloudFormation stack name (or `AGENTCORE_STACK_NAME` env var) |
| `-v` | Verbose output |
| `-vv` | Debug-level output |

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
| `MODEL_ID` | No | — | Bedrock model/inference profile ID (set via SSM) |
| `PARAMETER_STORE_PREFIX` | No | `/agentcore/sales-agent/` | SSM parameter path prefix |

At startup the agent reads configuration from AWS Systems Manager Parameter Store first, then falls back to environment variables for any missing values.
