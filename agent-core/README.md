# AgentCore CDK Infrastructure

AWS CDK infrastructure for deploying and managing a Bedrock AgentCore runtime with native tools for product search and recommendations. This project provides a complete solution for deploying a sales agent built with the Strands SDK, including VPC management, CI/CD pipeline, CLI tooling, and comprehensive monitoring.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [CLI Tool](#cli-tool)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Testing](#testing)

## Overview

This infrastructure deploys a containerized Bedrock AgentCore runtime with:

- **Native Tools**: Product search and recommendation tools embedded in the runtime
- **Multi-Stage Support**: Deploy isolated dev, staging, and production environments
- **CI/CD Pipeline**: Automated build and deployment with CodePipeline, CodeBuild, and CodeDeploy
- **Flexible VPC**: Use existing VPC or create new VPC with public/private subnets
- **Parameter Store**: Centralized configuration management
- **Graviton Architecture**: ARM64 containers for optimal price-performance
- **Comprehensive Monitoring**: CloudWatch logs, metrics, and alarms

### Key Features

- **Blue/Green Deployments**: Zero-downtime deployments with automatic rollback
- **AgentCore Memory**: 30-day conversation context retention
- **CLI Management**: Command-line tool for operations and invocations
- **Security**: Least-privilege IAM policies and VPC isolation
- **Observability**: OpenTelemetry instrumentation and structured logging

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Developer Workflow                        │
│  ┌──────────┐              ┌──────────────┐                     │
│  │Developer │─────────────▶│   CLI Tool   │                     │
│  └──────────┘              └──────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CI/CD Pipeline                           │
│  ┌────────────┐  ┌─────────────┐  ┌───────────┐  ┌──────────┐ │
│  │CodeCommit  │─▶│CodePipeline │─▶│CodeBuild  │─▶│CodeDeploy│ │
│  │Repository  │  │             │  │           │  │          │ │
│  └────────────┘  └─────────────┘  └───────────┘  └──────────┘ │
│                                           │                      │
│                                           ▼                      │
│                                    ┌─────────────┐              │
│                                    │ECR Repository│              │
│                                    └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Runtime Infrastructure                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                          VPC                             │   │
│  │  ┌──────────────────┐      ┌────────────────┐          │   │
│  │  │Runtime Container │─────▶│Parameter Store │          │   │
│  │  │  (ARM64/Graviton)│      └────────────────┘          │   │
│  │  └──────────────────┘              │                    │   │
│  │          │                          ▼                    │   │
│  │          │                  ┌────────────────┐          │   │
│  │          └─────────────────▶│CloudWatch Logs │          │   │
│  │                              └────────────────┘          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Services                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │DynamoDB  │  │OpenSearch│  │Personalize│  │AgentCore     │  │
│  │Tables    │  │Serverless│  │           │  │Memory        │  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Components

- **CDK Stack**: Infrastructure-as-code for all AWS resources
- **Runtime Container**: Python 3.13 application with Strands SDK and native tools
- **CLI Tool**: Management interface for parameters, invocations, and logs
- **CI/CD Pipeline**: Automated testing and deployment workflow
- **Data Layer**: DynamoDB, OpenSearch, Personalize, and AgentCore Memory

## Prerequisites

### Required

1. **AWS Account**: Active AWS account with appropriate permissions
2. **AWS CLI**: Version 2.x or later
   ```bash
   aws --version
   # aws-cli/2.x.x or later
   ```

3. **AWS CDK CLI**: Version 2.100.0 or later
   ```bash
   npm install -g aws-cdk
   cdk --version
   # 2.100.0 or later
   ```

4. **Python**: Version 3.13 or later
   ```bash
   python3 --version
   # Python 3.13.x or later
   ```

5. **Docker**: For building container images locally (optional)
   ```bash
   docker --version
   # Docker version 20.x or later
   ```

6. **uv**: Python package manager for faster dependency installation
   ```bash
   pip install uv
   ```

### AWS Credentials

Configure AWS credentials using one of these methods:

**Option 1: AWS CLI Configuration**
```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region, Output format
```

**Option 2: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Option 3: IAM Role** (for EC2/ECS)
- Attach IAM role with required permissions to your compute instance

### Required IAM Permissions

Your AWS credentials need permissions for:
- CloudFormation (create/update/delete stacks)
- IAM (create roles and policies)
- VPC (create/manage network resources)
- ECS/Fargate or App Runner (deploy runtime)
- ECR (create repositories, push images)
- CodeCommit, CodePipeline, CodeBuild, CodeDeploy
- Systems Manager Parameter Store
- CloudWatch Logs and Alarms
- Bedrock AgentCore Memory

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd agentcore-cdk-infrastructure

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install uv
uv pip install -r requirements.txt
uv pip install -r cli/requirements.txt
```

### 2. Prepare Required Resources

Before deployment, ensure these AWS resources exist:

- **DynamoDB Tables**: Product catalog and user profile tables
- **OpenSearch Serverless**: Collection with vector embeddings
- **Amazon Personalize**: Trained recommender

### 3. Deploy Infrastructure (Bootstrap Method)

The bootstrap deployment uses CodePipeline to orchestrate the deployment in the correct order, eliminating the need for local ARM64 Docker builds.

**Deploy with new VPC:**
```bash
./scripts/deploy_bootstrap.sh \
  --stage dev \
  --item-table my-items-table \
  --user-table my-users-table \
  --aoss-endpoint https://xxxxx.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-rec
```

**Deploy with existing VPC:**
```bash
./scripts/deploy_bootstrap.sh \
  --stage dev \
  --vpc-id vpc-0123456789abcdef0 \
  --item-table my-items-table \
  --user-table my-users-table \
  --aoss-endpoint https://xxxxx.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-rec
```

**What happens during bootstrap deployment:**
1. Deploys BootstrapStack (CodeCommit + CodePipeline)
2. Commits code to CodeCommit repository
3. Pipeline automatically deploys InfrastructureStack (VPC, ECR, IAM)
4. Pipeline builds ARM64 Docker image and pushes to ECR
5. Pipeline deploys RuntimeStack (ECS/Fargate with the built image)
6. Updates Parameter Store with AgentCore Memory ID

**Deployment time:** 10-15 minutes for first deployment

### 4. Test Runtime

```bash
# Invoke the agent
python cli/sales_agent_cli.py --stage dev invoke --message "Find me a blue dress"

# Check logs
python cli/sales_agent_cli.py --stage dev logs --tail 50

# Check status
python cli/sales_agent_cli.py --stage dev status
```

### 5. Subsequent Updates

After initial deployment, push code changes to trigger automatic redeployment:

```bash
git add .
git commit -m "Update runtime logic"
git push codecommit-dev main
```

The CodePipeline will automatically rebuild and redeploy.

## Deployment

### Bootstrap Deployment Strategy

This project uses a **two-phase bootstrap deployment** approach that solves the chicken-and-egg problem of deploying containerized applications with CDK. See [docs/BOOTSTRAP_DEPLOYMENT.md](docs/BOOTSTRAP_DEPLOYMENT.md) for detailed architecture documentation.

**Key Benefits:**
- No local ARM64 Docker builds required
- Automated CI/CD pipeline from day one
- Eliminates circular dependencies (ECR created before Docker build)
- Consistent build environment for all deployments
- Full traceability through CodePipeline console

### Deployment Script

The `deploy_bootstrap.sh` script orchestrates the bootstrap deployment workflow.

**Usage:**
```bash
./scripts/deploy_bootstrap.sh [OPTIONS]
```

**Required Options:**
- `--stage STAGE`: Stage name (dev, staging, prod, or custom)
- `--item-table TABLE`: DynamoDB items table name
- `--user-table TABLE`: DynamoDB users table name
- `--aoss-endpoint URL`: OpenSearch Serverless endpoint
- `--personalize-arn ARN`: Personalize recommender ARN

**Optional Options:**
- `--vpc-id VPC_ID`: Existing VPC ID (creates new VPC if not provided)
- `--destroy`: Tear down all stacks
- `--help`: Display help message

### Deployment Examples

**Example 1: Deploy dev environment with new VPC**
```bash
./scripts/deploy_bootstrap.sh \
  --stage dev \
  --item-table products-catalog \
  --user-table user-profiles \
  --aoss-endpoint https://abc123.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-rec
```

**Example 2: Deploy production with existing VPC**
```bash
./scripts/deploy_bootstrap.sh \
  --stage prod \
  --vpc-id vpc-0123456789abcdef0 \
  --item-table products-catalog-prod \
  --user-table user-profiles-prod \
  --aoss-endpoint https://xyz789.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/prod-rec
```

**Example 3: Deploy custom feature branch environment**
```bash
./scripts/deploy_bootstrap.sh \
  --stage feature-auth-v2 \
  --item-table products-catalog \
  --user-table user-profiles \
  --aoss-endpoint https://abc123.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-rec
```

**Example 4: Destroy staging environment**
```bash
./scripts/deploy_bootstrap.sh --stage staging --destroy
```

### Deployment Process

The bootstrap deployment executes in five phases:

**Phase 1: Bootstrap Stack Deployment**
- Deploys BootstrapStack containing CodeCommit, CodePipeline, CodeBuild
- Creates S3 artifact bucket and IAM roles
- No Docker images or ECR repositories required at this stage

**Phase 2: Code Commit**
- Initializes git repository (if not already initialized)
- Commits all source code to local repository
- Pushes code to CodeCommit repository
- Automatically triggers CodePipeline

**Phase 3: Pipeline Execution (Automated)**
1. Deploys InfrastructureStack (VPC, ECR, IAM, Parameter Store)
2. Builds ARM64 Docker image using CodeBuild on Graviton
3. Pushes Docker image to ECR repository
4. Deploys RuntimeStack (ECS/Fargate with the built image)

**Phase 4: Memory Update**
- Retrieves AgentCore Memory ID from stack outputs
- Updates Parameter Store with memory ID
- Enables runtime to access conversation history

**Phase 5: Verification**
- Displays all stack outputs (endpoints, URLs, etc.)
- Prompts user to verify service is working
- Suggests test command

### Stack Outputs

After successful deployment, you'll see:

```
Outputs:
BootstrapStack-dev.RepositoryUrl = https://git-codecommit.us-east-1.amazonaws.com/v1/repos/sales-agent-dev
BootstrapStack-dev.PipelineName = sales-agent-pipeline-dev
InfrastructureStack-dev.VpcId = vpc-0123456789abcdef0
InfrastructureStack-dev.EcrRepositoryUri = 123456789012.dkr.ecr.us-east-1.amazonaws.com/sales-agent-dev
InfrastructureStack-dev.MemoryId = mem-xxxxx
RuntimeStack-dev.ServiceEndpoint = sales-agent-dev-alb-xxxxx.us-east-1.elb.amazonaws.com
RuntimeStack-dev.LogGroupName = /aws/sales-agent/dev
```

### Monitoring Pipeline Execution

**View pipeline status in AWS Console:**
1. Navigate to CodePipeline console
2. Select pipeline: `sales-agent-pipeline-{stage}`
3. View execution progress and logs

**View pipeline status with CLI:**
```bash
aws codepipeline get-pipeline-state --pipeline-name sales-agent-pipeline-dev
```

### Updating Deployed Code

After initial deployment, push code changes to trigger automatic redeployment:

```bash
# Make code changes
git add .
git commit -m "feat(runtime): add new tool"
git push codecommit-dev main
```

The CodePipeline will automatically:
1. Detect the commit
2. Rebuild the Docker image
3. Deploy the updated RuntimeStack
4. Perform health checks
5. Complete deployment or rollback on failure

## CLI Tool

The CLI tool provides operational management for the runtime.

### Installation

```bash
# Install CLI dependencies
pip install uv
uv pip install -r cli/requirements.txt
```

### Commands

#### Parameter Management

**Set parameter value:**
```bash
python cli/sales_agent_cli.py --stage dev param set --key item_table --value my-table
```

**Get parameter value:**
```bash
python cli/sales_agent_cli.py --stage dev param get --key item_table
```

**List all parameters:**
```bash
python cli/sales_agent_cli.py --stage dev param list
```

#### Runtime Invocation

**Invoke with message:**
```bash
python cli/sales_agent_cli.py --stage dev invoke --message "Find me a blue dress"
```

**Invoke with session and actor:**
```bash
python cli/sales_agent_cli.py --stage dev invoke \
  --message "Show me recommendations" \
  --session-id session-123 \
  --actor-id user-456
```

**Interactive chat session:**
```bash
# Start interactive chat (normal mode)
python cli/sales_agent_cli.py --stage dev chat

# Start with verbose output (shows thinking content and performance metrics)
python cli/sales_agent_cli.py --stage dev chat -v

# Start with debug output (shows all raw streaming events)
python cli/sales_agent_cli.py --stage dev chat -vv
```

**Chat Features:**
- **Streaming Responses**: Real-time streaming with animated thinking indicator
- **Thinking Tag Filtering**: Internal reasoning hidden from normal output
- **Performance Metrics**: Connection time, TTFB, and total response time (verbose mode)
- **File Logging**: All events logged to `~/.sales-agent-cli/logs/chat-{timestamp}.log`
- **Multi-turn Conversations**: Session persistence across messages
- **Special Commands**:
  - `/exit`, `/quit`, `/q` - Exit chat session
  - `/clear` - Clear screen
  - `/session` - Show current session ID
  - `/help` - Show help message

**Verbosity Levels:**
- **Level 0** (default): Normal user output with thinking spinner and agent response
- **Level 1** (`-v`): + Thinking content + Performance metrics summary
- **Level 2** (`-vv`): + All raw streaming events + Detailed timing

**Example Output (Normal Mode):**
```
You: hello
Thinking: ⠋
Agent[7.0s]: Hello! How can I assist you today?
```

**Example Output (Verbose Mode `-v`):**
```
You: hello
Thinking: ⠋
[Thinking] The user has greeted me. I should acknowledge the greeting.
Agent[7.0s]: Hello! How can I assist you today?
[Metrics] Connection: 32ms, TTFB: 44ms, Total: 1045ms
```

#### Log Retrieval

**Get recent logs:**
```bash
python cli/sales_agent_cli.py --stage dev logs --tail 100
```

**Get logs for time range:**
```bash
python cli/sales_agent_cli.py --stage dev logs \
  --start "2024-01-01 10:00" \
  --end "2024-01-01 11:00"
```

#### Deployment Status

**Check runtime status:**
```bash
python cli/sales_agent_cli.py --stage dev status
```

Output:
```
Stage: dev
Status: ACTIVE
Health: HEALTHY
Version: abc1234
Last Deployment: 2024-01-15 14:30:00
Endpoint: https://xxxxx.execute-api.us-east-1.amazonaws.com
```

### CLI Help

Get help for any command:
```bash
python cli/sales_agent_cli.py --help
python cli/sales_agent_cli.py param --help
python cli/sales_agent_cli.py invoke --help
```

## Configuration

### Parameter Store Schema

All configuration is stored in AWS Systems Manager Parameter Store with hierarchical naming:

```
/sales-agent/{stage}/
├── item_table          # DynamoDB table name for product catalog
├── user_table          # DynamoDB table name for user profiles
├── aoss_endpoint       # OpenSearch Serverless endpoint URL
├── recommender_arn     # Amazon Personalize recommender ARN
├── s3_bucket           # S3 bucket name for product images
└── memory_id           # AgentCore Memory resource ID (auto-created)
```

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `item_table` | String | DynamoDB table with product data | `products-catalog` |
| `user_table` | String | DynamoDB table with user profiles | `user-profiles` |
| `aoss_endpoint` | String | OpenSearch Serverless collection endpoint | `https://xxxxx.us-east-1.aoss.amazonaws.com` |
| `recommender_arn` | String | Personalize recommender ARN | `arn:aws:personalize:us-east-1:123456789012:recommender/my-rec` |
| `memory_id` | String | AgentCore Memory ID (auto-created by pipeline) | `mem-xxxxx` |

**Note:** The `memory_id` parameter is automatically created and populated by the deployment pipeline. All other parameters must be provided during deployment via command-line arguments to `deploy_bootstrap.sh`.

### Setting Parameters

Parameters are set during deployment via command-line arguments:

```bash
./scripts/deploy_bootstrap.sh \
  --stage dev \
  --item-table products-catalog \
  --user-table user-profiles \
  --aoss-endpoint https://xxxxx.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-rec
```

The deployment script automatically:
1. Validates all required parameters
2. Creates Parameter Store entries during InfrastructureStack deployment
3. Updates `memory_id` after AgentCore Memory is created

### Environment Variables

The runtime container uses these environment variables (automatically configured by CDK):

- `MCP_REGION`: AWS region (default: us-east-1)
- `AGENTCORE_MEMORY_ID`: Memory resource ID (from Parameter Store)
- `AOSS_COLLECTION_ENDPOINT`: OpenSearch endpoint (from Parameter Store)
- `RECOMMENDER_ARN`: Personalize recommender ARN (from Parameter Store)

## Monitoring

### CloudWatch Logs

Runtime logs are sent to CloudWatch Logs with structured JSON format.

**Log Group**: `/aws/sales-agent/{stage}`

**View logs with CLI:**
```bash
python cli/sales_agent_cli.py --stage dev logs --tail 100
```

**View logs in AWS Console:**
1. Navigate to CloudWatch → Log groups
2. Select `/aws/sales-agent/dev`
3. View log streams

### CloudWatch Alarms

The stack creates alarms for:

1. **Error Rate Alarm**: Triggers when error rate exceeds 5%
2. **Latency Alarm**: Triggers when p99 latency exceeds 10 seconds

**Alarm Actions**: Publishes to SNS topic for notifications

### OpenTelemetry Metrics

The runtime emits OpenTelemetry metrics:

- **Tool Execution Duration**: Time taken for each tool invocation
- **Agent Invocation Duration**: End-to-end invocation time
- **Error Counts**: Number of errors by type

**View metrics in CloudWatch:**
1. Navigate to CloudWatch → Metrics
2. Select custom namespace: `SalesAgent`
3. View metrics by dimension (stage, tool_name, etc.)

### Health Checks

The runtime exposes health check endpoints:

- **Port 8000**: Primary application port
- **Port 8080**: Health check endpoint
- **Port 9000**: Metrics endpoint

## Troubleshooting

### Common Issues

#### 1. Deployment Fails: "AWS credentials not configured"

**Problem**: AWS CLI cannot find valid credentials

**Solution**:
```bash
# Configure credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# Verify credentials
aws sts get-caller-identity
```

#### 2. Deployment Fails: "CDK not bootstrapped"

**Problem**: CDK bootstrap stack not created in account/region

**Solution**:
```bash
# Bootstrap CDK
cdk bootstrap aws://ACCOUNT-ID/REGION

# Or let deploy script handle it
./scripts/deploy.sh --stage dev
```

#### 3. Runtime Fails: "Parameter not found"

**Problem**: Required Parameter Store values not set

**Solution**:
```bash
# List current parameters
python cli/sales_agent_cli.py --stage dev param list

# Set missing parameters
python cli/sales_agent_cli.py --stage dev param set --key item_table --value your-table-name
```

#### 4. Invocation Fails: "Access Denied"

**Problem**: Runtime IAM role lacks permissions

**Solution**:
- Verify DynamoDB table names match Parameter Store values
- Verify OpenSearch collection ARN in IAM policy
- Verify Personalize recommender ARN in IAM policy
- Check CloudWatch logs for specific permission errors

#### 5. Build Fails: "Platform mismatch"

**Problem**: Building ARM64 image on non-ARM64 host

**Solution**:
```bash
# Use Docker buildx for cross-platform builds
docker buildx build --platform linux/arm64 -t runtime:latest runtime/

# Or ensure CodeBuild uses ARM64 compute type
```

#### 6. CLI Command Fails: "Stage not found"

**Problem**: Stage doesn't exist or parameters not set

**Solution**:
```bash
# Verify stack exists
aws cloudformation describe-stacks --stack-name SalesAgentRuntimeStack-dev

# Verify parameters exist
aws ssm get-parameters-by-path --path /sales-agent/dev/
```

### Debugging Tips

**Check CloudFormation Events:**
```bash
aws cloudformation describe-stack-events --stack-name SalesAgentRuntimeStack-dev --max-items 20
```

**Check Runtime Logs:**
```bash
python cli/sales_agent_cli.py --stage dev logs --tail 100
```

**Check Parameter Store:**
```bash
aws ssm get-parameters-by-path --path /sales-agent/dev/ --recursive
```

**Check IAM Role Permissions:**
```bash
aws iam get-role --role-name SalesAgentRuntimeStack-dev-RuntimeRole
aws iam list-attached-role-policies --role-name SalesAgentRuntimeStack-dev-RuntimeRole
```

**Test Runtime Connectivity:**
```bash
# Test from within VPC
curl https://your-runtime-endpoint/health
```

### Getting Help

If you encounter issues not covered here:

1. Check CloudWatch logs for detailed error messages
2. Review CloudFormation stack events for deployment failures
3. Verify all prerequisites are installed and configured
4. Ensure AWS credentials have required permissions
5. Check AWS service quotas and limits

## Development

### Project Structure

```
agentcore-cdk-infrastructure/
├── cdk/                      # CDK infrastructure code
│   ├── app.py               # CDK app entry point
│   ├── cdk.json             # CDK configuration
│   └── stacks/
│       └── sales_agent_stack.py  # Main stack definition
├── runtime/                  # Runtime application
│   ├── Dockerfile           # Container image definition
│   ├── requirements.txt     # Python dependencies
│   └── strands_agent.py     # Agent implementation
├── cli/                      # CLI tool
│   ├── requirements.txt     # CLI dependencies
│   └── sales_agent_cli.py   # CLI implementation
├── scripts/                  # Deployment scripts
│   ├── deploy.sh            # Main deployment script
│   └── validate_environment.sh  # Environment validation
├── tests/                    # Test suite
│   ├── unit/                # Unit tests
│   ├── property/            # Property-based tests
│   └── integration/         # Integration tests
├── buildspec.yml            # CodeBuild configuration
├── requirements.txt         # CDK dependencies
└── README.md               # This file
```

### Local Development

**Setup development environment:**
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install uv
uv pip install -r requirements.txt
uv pip install -r runtime/requirements.txt
uv pip install -r cli/requirements.txt

# Install development dependencies
uv pip install pytest pytest-cov hypothesis moto boto3-stubs
```

**Run tests:**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/property/
```

**Synthesize CDK stack:**
```bash
cd cdk
cdk synth
```

**Build runtime container locally:**
```bash
cd runtime
docker build --platform linux/arm64 -t sales-agent-runtime:latest .
```

### Making Changes

**Modify CDK infrastructure:**
1. Edit `cdk/stacks/sales_agent_stack.py`
2. Run `cdk synth` to validate
3. Run unit tests: `pytest tests/unit/test_cdk_stack.py`
4. Deploy: `./scripts/deploy.sh --stage dev`

**Modify runtime application:**
1. Edit `runtime/strands_agent.py`
2. Run unit tests: `pytest tests/unit/test_runtime.py`
3. Build container: `docker build runtime/`
4. Push to CodeCommit to trigger CI/CD

**Modify CLI tool:**
1. Edit `cli/sales_agent_cli.py`
2. Run unit tests: `pytest tests/unit/test_cli_*.py`
3. Test locally: `python cli/sales_agent_cli.py --stage dev status`

### CI/CD Workflow

**Automated pipeline:**
1. Push code to CodeCommit repository
2. CodePipeline triggers on commit to main branch
3. CodeBuild runs unit tests
4. CodeBuild builds ARM64 Docker image
5. CodeBuild pushes image to ECR
6. CodeDeploy performs blue/green deployment
7. Health checks validate new version
8. Traffic shifts to new version
9. Old version terminated

**Manual deployment:**
```bash
# Deploy via script
./scripts/deploy.sh --stage dev

# Or use CDK directly
cd cdk
cdk deploy --context stage=dev
```

## Testing

### Test Suites

**Unit Tests**: Test individual components in isolation
```bash
pytest tests/unit/
```

**Property-Based Tests**: Test universal correctness properties
```bash
pytest tests/property/
```

**Integration Tests**: Test end-to-end workflows
```bash
pytest tests/integration/
```

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=. --cov-report=html --cov-report=term
```

**Run specific test file:**
```bash
pytest tests/unit/test_cdk_stack.py
```

**Run specific test:**
```bash
pytest tests/unit/test_cdk_stack.py::test_vpc_creation
```

### Test Coverage

Target: 85%+ code coverage

**View coverage report:**
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

### Property-Based Tests

The project uses Hypothesis for property-based testing to validate universal correctness properties:

- **Property 1**: Parameter Store hierarchical naming
- **Property 2**: No wildcard IAM permissions
- **Property 3**: Stage-prefixed resource naming
- **Property 4**: Multi-stage deployment isolation
- **Property 5**: Universal stage tagging

Run property tests:
```bash
pytest tests/property/ -v
```

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]

## Support

For issues and questions:
- GitHub Issues: [Your Repository Issues URL]
- Documentation: [Your Documentation URL]
- AWS Support: [AWS Support URL]
