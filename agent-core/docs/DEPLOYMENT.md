# Deployment Guide

This comprehensive guide walks you through deploying the AgentCore CDK Infrastructure from initial setup to production deployment, including configuration examples, security best practices, and monitoring setup.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Deployment Scenarios](#deployment-scenarios)
- [Configuration Management](#configuration-management)
- [Security Best Practices](#security-best-practices)
- [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
- [Multi-Stage Deployment](#multi-stage-deployment)
- [CI/CD Pipeline Setup](#cicd-pipeline-setup)
- [Rollback Procedures](#rollback-procedures)
- [Production Checklist](#production-checklist)

## Prerequisites

### Required Tools

Ensure all required tools are installed and configured:

**1. AWS CLI**
```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Verify installation
aws --version
# Expected: aws-cli/2.x.x or later
```

**2. AWS CDK CLI**
```bash
# Install CDK globally
npm install -g aws-cdk

# Verify installation
cdk --version
# Expected: 2.100.0 or later
```

**3. Python 3.13+**
```bash
# Verify Python version
python3 --version
# Expected: Python 3.13.x or later

# Install uv for faster package management
pip install uv
```

**4. Docker** (Optional, for local testing)
```bash
# Verify Docker installation
docker --version
# Expected: Docker version 20.x or later
```

### AWS Account Setup

**1. Create AWS Account**
- Sign up at https://aws.amazon.com
- Complete account verification
- Set up billing alerts

**2. Configure IAM User**

Create an IAM user with required permissions:

```bash
# Create IAM user
aws iam create-user --user-name cdk-deployer

# Attach required policies
aws iam attach-user-policy \
  --user-name cdk-deployer \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Create access key
aws iam create-access-key --user-name cdk-deployer
```

**Note**: For production, use more restrictive policies. See [Security Best Practices](#security-best-practices).

**3. Configure AWS Credentials**

```bash
# Configure credentials
aws configure

# Enter when prompted:
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region name: us-east-1
# Default output format: json

# Verify credentials
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDAI23EXAMPLEID456",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/cdk-deployer"
}
```

## Initial Setup

### Step 1: Clone Repository

```bash
# Clone the repository
git clone <repository-url>
cd agentcore-cdk-infrastructure

# Verify project structure
ls -la
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Verify activation (prompt should show (.venv))
which python
# Expected: /path/to/agentcore-cdk-infrastructure/.venv/bin/python
```

### Step 3: Install Dependencies

```bash
# Install uv for faster package management
pip install uv

# Install CDK dependencies
uv pip install -r requirements.txt

# Install runtime dependencies (for local testing)
uv pip install -r runtime/requirements.txt

# Install CLI dependencies
uv pip install -r cli/requirements.txt

# Install development dependencies
uv pip install pytest pytest-cov hypothesis moto boto3-stubs
```

### Step 4: Bootstrap CDK

Bootstrap CDK in your AWS account and region:

```bash
# Bootstrap CDK
cdk bootstrap aws://ACCOUNT-ID/REGION

# Example
cdk bootstrap aws://123456789012/us-east-1
```

Expected output:
```
 ✅  Environment aws://123456789012/us-east-1 bootstrapped.
```

**What bootstrapping does**:
- Creates CDKToolkit CloudFormation stack
- Creates S3 bucket for CDK assets
- Creates IAM roles for CDK operations
- Sets up ECR repository for Docker images

### Step 5: Verify Setup

```bash
# Run tests to verify setup
pytest tests/unit/ -v

# Synthesize CDK stack to verify configuration
cd cdk
cdk synth
cd ..
```

## Deployment Scenarios

### Scenario 1: Development Environment (New VPC)

Deploy a development environment with a new VPC for testing and development.

**Step 1: Deploy Infrastructure**
```bash
./scripts/deploy.sh --stage dev
```

**Step 2: Wait for Deployment**
- Deployment typically takes 10-15 minutes
- Monitor progress in CloudFormation console
- Script will display outputs when complete

**Step 3: Configure Parameters**
```bash
# Set DynamoDB table names
python cli/sales_agent_cli.py --stage dev param set \
  --key item_table --value dev-products-catalog

python cli/sales_agent_cli.py --stage dev param set \
  --key user_table --value dev-user-profiles

# Set OpenSearch endpoint (replace with your endpoint)
python cli/sales_agent_cli.py --stage dev param set \
  --key aoss_endpoint --value https://xxxxx.us-east-1.aoss.amazonaws.com

# Set Personalize recommender ARN (replace with your ARN)
python cli/sales_agent_cli.py --stage dev param set \
  --key recommender_arn --value arn:aws:personalize:us-east-1:123456789012:recommender/dev-rec

# Set S3 bucket for images
python cli/sales_agent_cli.py --stage dev param set \
  --key s3_bucket --value dev-product-images
```

**Step 4: Verify Deployment**
```bash
# Check runtime status
python cli/sales_agent_cli.py --stage dev status

# Test invocation
python cli/sales_agent_cli.py --stage dev invoke \
  --message "Hello, can you help me find products?"

# Check logs
python cli/sales_agent_cli.py --stage dev logs --tail 50
```

### Scenario 2: Production Environment (Existing VPC)

Deploy a production environment using an existing VPC with pre-configured networking.

**Prerequisites**:
- Existing VPC with public and private subnets
- NAT gateways configured
- VPC endpoints for DynamoDB, S3, SSM (recommended)

**Step 1: Identify VPC ID**
```bash
# List VPCs
aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,Tags[?Key==`Name`].Value|[0]]' --output table

# Note your VPC ID (e.g., vpc-0123456789abcdef0)
```

**Step 2: Deploy with Existing VPC**
```bash
./scripts/deploy.sh --stage prod --vpc-id vpc-0123456789abcdef0
```

**Step 3: Configure Production Parameters**
```bash
# Set production DynamoDB tables
python cli/sales_agent_cli.py --stage prod param set \
  --key item_table --value prod-products-catalog

python cli/sales_agent_cli.py --stage prod param set \
  --key user_table --value prod-user-profiles

# Set production OpenSearch endpoint
python cli/sales_agent_cli.py --stage prod param set \
  --key aoss_endpoint --value https://prod-xxxxx.us-east-1.aoss.amazonaws.com

# Set production Personalize recommender
python cli/sales_agent_cli.py --stage prod param set \
  --key recommender_arn --value arn:aws:personalize:us-east-1:123456789012:recommender/prod-rec

# Set production S3 bucket
python cli/sales_agent_cli.py --stage prod param set \
  --key s3_bucket --value prod-product-images
```

**Step 4: Production Verification**
```bash
# Verify status
python cli/sales_agent_cli.py --stage prod status

# Run smoke tests
python cli/sales_agent_cli.py --stage prod invoke \
  --message "Test message" \
  --session-id smoke-test-$(date +%s)

# Monitor logs
python cli/sales_agent_cli.py --stage prod logs --tail 100
```

### Scenario 3: Staging Environment (Clone of Production)

Deploy a staging environment that mirrors production configuration.

**Step 1: Deploy Staging Stack**
```bash
./scripts/deploy.sh --stage staging --vpc-id vpc-0123456789abcdef0
```

**Step 2: Copy Production Configuration**
```bash
# Script to copy parameters from prod to staging
for key in item_table user_table aoss_endpoint recommender_arn s3_bucket; do
  value=$(python cli/sales_agent_cli.py --stage prod param get --key $key | cut -d: -f2 | xargs)
  # Modify value for staging (e.g., replace "prod" with "staging")
  staging_value=$(echo $value | sed 's/prod/staging/g')
  python cli/sales_agent_cli.py --stage staging param set --key $key --value "$staging_value"
done
```

**Step 3: Verify Staging**
```bash
# Compare configurations
echo "=== Production ==="
python cli/sales_agent_cli.py --stage prod param list

echo "=== Staging ==="
python cli/sales_agent_cli.py --stage staging param list

# Test staging
python cli/sales_agent_cli.py --stage staging invoke --message "Test staging environment"
```

### Scenario 4: Feature Branch Environment

Deploy a temporary environment for testing a specific feature branch.

**Step 1: Deploy Feature Environment**
```bash
# Use feature name as stage
./scripts/deploy.sh --stage feature-auth-v2
```

**Step 2: Configure with Test Data**
```bash
# Use test/mock data sources
python cli/sales_agent_cli.py --stage feature-auth-v2 param set \
  --key item_table --value test-products

python cli/sales_agent_cli.py --stage feature-auth-v2 param set \
  --key user_table --value test-users

# Use dev OpenSearch and Personalize
python cli/sales_agent_cli.py --stage feature-auth-v2 param set \
  --key aoss_endpoint --value https://dev-xxxxx.us-east-1.aoss.amazonaws.com

python cli/sales_agent_cli.py --stage feature-auth-v2 param set \
  --key recommender_arn --value arn:aws:personalize:us-east-1:123456789012:recommender/dev-rec

python cli/sales_agent_cli.py --stage feature-auth-v2 param set \
  --key s3_bucket --value test-images
```

**Step 3: Test Feature**
```bash
# Test new feature
python cli/sales_agent_cli.py --stage feature-auth-v2 invoke \
  --message "Test new authentication feature"
```

**Step 4: Cleanup When Done**
```bash
# Destroy feature environment
./scripts/deploy.sh --stage feature-auth-v2 --destroy
```

## Configuration Management

### Parameter Store Best Practices

**1. Naming Convention**

Use consistent naming across stages:
```
/sales-agent/{stage}/{key}
```

**2. Parameter Organization**

Group related parameters:
```
# Data sources
/sales-agent/prod/item_table
/sales-agent/prod/user_table

# AI services
/sales-agent/prod/aoss_endpoint
/sales-agent/prod/recommender_arn

# Storage
/sales-agent/prod/s3_bucket

# Runtime
/sales-agent/prod/memory_id
```

**3. Secure Sensitive Values**

Use SecureString type for sensitive data:
```bash
# Set as SecureString (encrypted with KMS)
aws ssm put-parameter \
  --name /sales-agent/prod/api_key \
  --value "sensitive-value" \
  --type SecureString
```

**4. Version Control**

Track parameter changes:
```bash
# Get parameter history
aws ssm get-parameter-history \
  --name /sales-agent/prod/item_table
```

### Configuration Templates

**Development Configuration**:
```bash
# dev-config.sh
export STAGE=dev
export ITEM_TABLE=dev-products-catalog
export USER_TABLE=dev-user-profiles
export AOSS_ENDPOINT=https://dev-xxxxx.us-east-1.aoss.amazonaws.com
export RECOMMENDER_ARN=arn:aws:personalize:us-east-1:123456789012:recommender/dev-rec
export S3_BUCKET=dev-product-images
```

**Production Configuration**:
```bash
# prod-config.sh
export STAGE=prod
export ITEM_TABLE=prod-products-catalog
export USER_TABLE=prod-user-profiles
export AOSS_ENDPOINT=https://prod-xxxxx.us-east-1.aoss.amazonaws.com
export RECOMMENDER_ARN=arn:aws:personalize:us-east-1:123456789012:recommender/prod-rec
export S3_BUCKET=prod-product-images
```

**Apply Configuration**:
```bash
# Source configuration
source prod-config.sh

# Apply parameters
python cli/sales_agent_cli.py --stage $STAGE param set --key item_table --value $ITEM_TABLE
python cli/sales_agent_cli.py --stage $STAGE param set --key user_table --value $USER_TABLE
python cli/sales_agent_cli.py --stage $STAGE param set --key aoss_endpoint --value $AOSS_ENDPOINT
python cli/sales_agent_cli.py --stage $STAGE param set --key recommender_arn --value $RECOMMENDER_ARN
python cli/sales_agent_cli.py --stage $STAGE param set --key s3_bucket --value $S3_BUCKET
```

## Security Best Practices

### IAM Policies

**1. Least Privilege Runtime Role**

The runtime execution role should have minimal permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query",
                "dynamodb:GetItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:us-east-1:123456789012:table/prod-products-catalog",
                "arn:aws:dynamodb:us-east-1:123456789012:table/prod-user-profiles"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "aoss:APIAccessAll",
            "Resource": "arn:aws:aoss:us-east-1:123456789012:collection/prod-collection-id"
        },
        {
            "Effect": "Allow",
            "Action": "personalize:GetRecommendations",
            "Resource": "arn:aws:personalize:us-east-1:123456789012:recommender/prod-rec"
        },
        {
            "Effect": "Allow",
            "Action": "bedrock:InvokeModel",
            "Resource": [
                "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-image-v1",
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                "arn:aws:bedrock:us-east-1::foundation-model/us.amazon.nova-lite-v1:0"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParametersByPath"
            ],
            "Resource": "arn:aws:ssm:us-east-1:123456789012:parameter/sales-agent/prod/*"
        }
    ]
}
```

**2. Deployer Role Permissions**

For production deployments, use a dedicated deployer role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:*",
                "iam:*",
                "ec2:*",
                "ecs:*",
                "ecr:*",
                "codecommit:*",
                "codepipeline:*",
                "codebuild:*",
                "codedeploy:*",
                "ssm:*",
                "logs:*",
                "s3:*"
            ],
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "aws:RequestedRegion": "us-east-1"
                }
            }
        }
    ]
}
```

### Network Security

**1. VPC Configuration**

- Deploy runtime in private subnets
- Use NAT gateways for outbound internet access
- Configure VPC endpoints for AWS services
- Implement network ACLs for additional security

**2. Security Groups**

Runtime security group configuration:

```python
# Inbound rules
- Port 8000: From VPC CIDR (application traffic)
- Port 8080: From VPC CIDR (health checks)
- Port 9000: From VPC CIDR (metrics)

# Outbound rules
- Port 443: To 0.0.0.0/0 (HTTPS to AWS services)
```

**3. VPC Endpoints**

Create VPC endpoints to avoid NAT gateway costs:

```bash
# DynamoDB endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0123456789abcdef0 \
  --service-name com.amazonaws.us-east-1.dynamodb \
  --route-table-ids rtb-12345678

# S3 endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0123456789abcdef0 \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-12345678

# Systems Manager endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0123456789abcdef0 \
  --service-name com.amazonaws.us-east-1.ssm \
  --vpc-endpoint-type Interface \
  --subnet-ids subnet-12345678 subnet-87654321
```

### Encryption

**1. Data at Rest**

- Parameter Store: Use SecureString with KMS encryption
- CloudWatch Logs: Enable server-side encryption
- ECR: Enable image scanning and encryption
- S3: Enable default encryption with KMS

**2. Data in Transit**

- All API calls use TLS 1.2+
- VPC endpoints use AWS PrivateLink
- Internal communication within VPC

### Secrets Management

**Never hardcode secrets**. Use Parameter Store or Secrets Manager:

```bash
# Store API key in Secrets Manager
aws secretsmanager create-secret \
  --name /sales-agent/prod/api-key \
  --secret-string "your-secret-value"

# Reference in code
import boto3
secrets = boto3.client('secretsmanager')
secret = secrets.get_secret_value(SecretId='/sales-agent/prod/api-key')
```

## Monitoring and Troubleshooting

### CloudWatch Dashboards

**Create Custom Dashboard**:

```bash
# Create dashboard JSON
cat > dashboard.json << 'EOF'
{
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["SalesAgent", "InvocationCount", {"stat": "Sum"}],
                    [".", "ErrorCount", {"stat": "Sum"}],
                    [".", "Latency", {"stat": "Average"}]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-east-1",
                "title": "Runtime Metrics"
            }
        }
    ]
}
EOF

# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name SalesAgent-prod \
  --dashboard-body file://dashboard.json
```

### CloudWatch Alarms

**Configure Alarms**:

```bash
# Error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name sales-agent-prod-error-rate \
  --alarm-description "Alert when error rate exceeds 5%" \
  --metric-name ErrorRate \
  --namespace SalesAgent \
  --statistic Average \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Latency alarm
aws cloudwatch put-metric-alarm \
  --alarm-name sales-agent-prod-latency \
  --alarm-description "Alert when latency exceeds 10 seconds" \
  --metric-name Latency \
  --namespace SalesAgent \
  --statistic Average \
  --period 300 \
  --threshold 10000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Log Analysis

**Query CloudWatch Logs Insights**:

```sql
# Find errors in last hour
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100

# Analyze tool execution times
fields @timestamp, tool_name, duration
| filter @message like /Tool execution/
| stats avg(duration), max(duration), min(duration) by tool_name

# Count invocations by user
fields @timestamp, actor_id
| filter @message like /Agent invocation/
| stats count() by actor_id
| sort count() desc
```

### Common Issues and Solutions

**Issue 1: Deployment Fails - "CDK not bootstrapped"**

Solution:
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

**Issue 2: Runtime Fails - "Parameter not found"**

Solution:
```bash
# List parameters
python cli/sales_agent_cli.py --stage prod param list

# Set missing parameters
python cli/sales_agent_cli.py --stage prod param set --key item_table --value your-table
```

**Issue 3: Invocation Fails - "Access Denied"**

Solution:
```bash
# Check IAM role permissions
aws iam get-role --role-name SalesAgentRuntimeStack-prod-RuntimeRole

# Verify resource ARNs match Parameter Store values
python cli/sales_agent_cli.py --stage prod param list
```

**Issue 4: High Latency**

Solution:
```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace SalesAgent \
  --metric-name Latency \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600 \
  --statistics Average

# Analyze logs for slow operations
python cli/sales_agent_cli.py --stage prod logs --tail 1000 | grep "duration"
```

**Issue 5: CodeDeploy Deployment Timeout**

**Symptoms**:
- Deployment times out after 60 minutes
- Error: "The deployment timed out while waiting for the replacement task set to become healthy"
- ECS tasks start but immediately exit

**Cause**: Runtime application exits because Parameter Store values are placeholders

**Diagnosis**:
```bash
# Check Parameter Store values
aws ssm get-parameters-by-path --path /sales-agent/dev/ --recursive

# Check ECS task logs
python cli/sales_agent_cli.py --stage dev logs --tail 100

# Look for errors like:
# "Required parameter /sales-agent/dev/item_table has placeholder value"
# "Cannot connect to DynamoDB table: PLACEHOLDER"
# "sys.exit(1)" in logs
```

**Solution**:
```bash
# Set all required Parameter Store values BEFORE pushing code
python cli/sales_agent_cli.py --stage dev param set --key item_table --value dev-products-catalog
python cli/sales_agent_cli.py --stage dev param set --key user_table --value dev-user-profiles
python cli/sales_agent_cli.py --stage dev param set --key aoss_endpoint --value https://xxxxx.us-east-1.aoss.amazonaws.com
python cli/sales_agent_cli.py --stage dev param set --key recommender_arn --value arn:aws:personalize:us-east-1:123456789012:recommender/dev-rec
python cli/sales_agent_cli.py --stage dev param set --key s3_bucket --value dev-product-images

# Verify all parameters are set
python cli/sales_agent_cli.py --stage dev param list

# Now push code to trigger deployment
git push codecommit main
```

**Important**: The placeholder image doesn't validate Parameter Store values, so the initial deployment succeeds. The real runtime application validates all parameters and exits if they're invalid. This is by design - it prevents the runtime from starting with incorrect configuration.

**Issue 6: Placeholder Image Still Running After Pipeline Completes**

**Symptoms**:
- Pipeline shows successful deployment
- But runtime doesn't respond to API calls
- Health checks pass but application doesn't work

**Cause**: Blue/green deployment may have failed silently, or traffic didn't shift

**Diagnosis**:
```bash
# Check which image is running
aws ecs describe-tasks \
  --cluster sales-agent-cluster-dev \
  --tasks $(aws ecs list-tasks --cluster sales-agent-cluster-dev --service-name sales-agent-service-dev --query 'taskArns[0]' --output text) \
  --query 'tasks[0].containers[0].image' \
  --output text

# If output contains "placeholder", the real image didn't deploy
```

**Solution**:
```bash
# Check CodeDeploy deployment status
aws deploy get-deployment \
  --deployment-id $(aws deploy list-deployments --application-name sales-agent-app-dev --query 'deployments[0]' --output text)

# If deployment failed, check logs
python cli/sales_agent_cli.py --stage dev logs --tail 200

# Retry deployment by pushing a new commit
git commit --allow-empty -m "chore: trigger redeployment"
git push codecommit main
```

## Multi-Stage Deployment

### Stage Isolation

Each stage is completely isolated:

- Separate VPCs (or separate subnets in shared VPC)
- Separate Parameter Store paths
- Separate IAM roles
- Separate CloudWatch log groups
- Separate ECR repositories

### Promotion Workflow

**Dev → Staging → Production**:

```bash
# 1. Deploy and test in dev
./scripts/deploy.sh --stage dev
# ... test thoroughly ...

# 2. Promote to staging
./scripts/deploy.sh --stage staging
# Copy configuration from dev (with staging-specific values)
# ... test thoroughly ...

# 3. Promote to production
./scripts/deploy.sh --stage prod
# Copy configuration from staging (with prod-specific values)
# ... monitor closely ...
```

### Configuration Promotion

**Script to promote configuration**:

```bash
#!/bin/bash
# promote-config.sh

SOURCE_STAGE=$1
TARGET_STAGE=$2

if [ -z "$SOURCE_STAGE" ] || [ -z "$TARGET_STAGE" ]; then
    echo "Usage: ./promote-config.sh SOURCE_STAGE TARGET_STAGE"
    exit 1
fi

echo "Promoting configuration from $SOURCE_STAGE to $TARGET_STAGE"

# Get all parameters from source
aws ssm get-parameters-by-path \
  --path /sales-agent/$SOURCE_STAGE/ \
  --recursive \
  --query 'Parameters[*].[Name,Value]' \
  --output text | while read name value; do
    # Extract key from path
    key=$(echo $name | awk -F/ '{print $NF}')
    
    # Modify value for target stage (replace stage name in values)
    target_value=$(echo $value | sed "s/$SOURCE_STAGE/$TARGET_STAGE/g")
    
    # Set in target stage
    python cli/sales_agent_cli.py --stage $TARGET_STAGE param set \
      --key $key --value "$target_value"
    
    echo "✓ Promoted $key"
done

echo "Configuration promotion complete"
```

Usage:
```bash
chmod +x promote-config.sh
./promote-config.sh dev staging
./promote-config.sh staging prod
```

## Placeholder Image Solution

### The Chicken-and-Egg Problem

When deploying the AgentCore infrastructure for the first time, there's a circular dependency:

1. The ECS service needs a container image to start
2. The ECR repository is created by CDK deployment
3. The CI/CD pipeline builds and pushes the real runtime image
4. But the pipeline only runs AFTER the stack is deployed
5. The stack deployment fails if ECS can't pull an image

**Solution**: CDK automatically builds and pushes a minimal placeholder image during deployment.

### How It Works

The CDK stack uses `DockerImageAsset` to handle the placeholder image:

```python
# In cdk/stacks/sales_agent_stack.py
placeholder_image_asset = ecr_assets.DockerImageAsset(
    self,
    f"PlaceholderImageAsset-{self.stage}",
    directory="runtime",
    file="Dockerfile.placeholder",
    platform=ecr_assets.Platform.LINUX_ARM64,
)

# ECS task definition uses the placeholder image initially
self.container = self.task_definition.add_container(
    f"RuntimeContainer-{self.stage}",
    image=ecs.ContainerImage.from_docker_image_asset(placeholder_image_asset),
    # ... other configuration
)
```

**What happens during deployment**:

1. CDK synthesizes the CloudFormation template
2. CDK builds the placeholder image from `runtime/Dockerfile.placeholder`
3. CDK pushes the placeholder image to ECR (created during deployment)
4. CloudFormation creates the ECS service with the placeholder image
5. ECS successfully starts with a minimal HTTP server
6. Deployment completes successfully

**What the placeholder image does**:

- Runs a minimal Python HTTP server on port 8000
- Responds to health checks at `/health` endpoint
- Returns "OK - Placeholder Runtime" message
- Handles SIGTERM gracefully for clean shutdowns
- Uses ARM64 architecture (Graviton) matching production

**After deployment**:

1. Push your runtime code to CodeCommit
2. CI/CD pipeline automatically triggers
3. Pipeline builds the real runtime image
4. CodeDeploy performs blue/green deployment
5. Real runtime image replaces the placeholder
6. Application is fully functional

### Placeholder Image Details

The placeholder image is defined in `runtime/Dockerfile.placeholder`:

```dockerfile
FROM --platform=linux/arm64 python:3.13-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore

# Minimal health check endpoint
# ... (see file for complete implementation)

EXPOSE 8000 8080 9000
CMD ["python", "-u", "/app/placeholder.py"]
```

**Key features**:
- ARM64 architecture for Graviton compatibility
- Minimal dependencies (Python + curl)
- Non-root user for security
- Health check endpoint for ECS
- Graceful signal handling
- Small image size (~150MB)

### Troubleshooting Placeholder Issues

**Issue**: Deployment fails with "CannotPullContainerError"

**Cause**: CDK failed to build or push the placeholder image

**Solution**:
```bash
# Verify Docker is running
docker ps

# Check if placeholder Dockerfile exists
ls -la runtime/Dockerfile.placeholder

# Manually build and test placeholder image
docker build --platform linux/arm64 -t placeholder-test -f runtime/Dockerfile.placeholder runtime/
docker run -p 8000:8000 placeholder-test

# Test health check
curl http://localhost:8000/health
# Expected: OK - Placeholder Runtime
```

**Issue**: ECS tasks exit with code 137 (SIGKILL)

**Cause**: Health checks failing (curl not installed in placeholder)

**Solution**: The current placeholder image includes curl. If you modify it, ensure curl is installed:
```dockerfile
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
```

**Issue**: Deployment succeeds but runtime doesn't work

**Cause**: Placeholder image is still running (CI/CD pipeline hasn't replaced it yet)

**Solution**:
```bash
# Check if real runtime image has been pushed
aws ecr describe-images --repository-name sales-agent-runtime-dev --region us-east-1

# Check pipeline status
aws codepipeline get-pipeline-state --name sales-agent-pipeline-dev

# If pipeline hasn't run, push code to CodeCommit
git push codecommit main
```

### Parameter Store Configuration

After the placeholder image is running, you need to configure Parameter Store values for the real runtime to work:

```bash
# The placeholder doesn't need these, but the real runtime does
python cli/sales_agent_cli.py --stage dev param set --key item_table --value dev-products-catalog
python cli/sales_agent_cli.py --stage dev param set --key user_table --value dev-user-profiles
python cli/sales_agent_cli.py --stage dev param set --key aoss_endpoint --value https://xxxxx.us-east-1.aoss.amazonaws.com
python cli/sales_agent_cli.py --stage dev param set --key recommender_arn --value arn:aws:personalize:us-east-1:123456789012:recommender/dev-rec
python cli/sales_agent_cli.py --stage dev param set --key s3_bucket --value dev-product-images
```

**Important**: The real runtime application will exit immediately if these parameters are set to "PLACEHOLDER" or are missing. This is expected behavior - the placeholder image keeps the ECS service healthy until the real runtime is deployed with proper configuration.

## CI/CD Pipeline Setup

### Complete Deployment Flow

Understanding the full deployment lifecycle helps troubleshoot issues:

**Phase 1: Initial CDK Deployment**
```
1. Run: ./scripts/deploy.sh --stage dev
2. CDK synthesizes CloudFormation template
3. CDK builds placeholder image from runtime/Dockerfile.placeholder
4. CDK pushes placeholder image to ECR (created during deployment)
5. CloudFormation creates all infrastructure resources
6. ECS service starts with placeholder image
7. Placeholder responds to health checks → ECS service HEALTHY
8. Deployment completes successfully ✓
```

**Phase 2: Code Push and CI/CD**
```
1. Push runtime code to CodeCommit repository
2. CodePipeline automatically triggers on commit
3. CodeBuild builds real runtime Docker image
4. CodeBuild pushes real image to ECR
5. CodeDeploy performs blue/green deployment
6. New tasks start with real runtime image
7. Health checks pass → traffic shifts to new tasks
8. Old placeholder tasks terminated
9. Real runtime is now serving traffic ✓
```

**Phase 3: Ongoing Updates**
```
1. Make code changes and commit
2. Push to CodeCommit
3. Pipeline automatically builds and deploys
4. Blue/green deployment ensures zero downtime
5. Automatic rollback if health checks fail
```

### Initial Pipeline Configuration

After deploying the stack, the CI/CD pipeline is automatically created but needs initial code push:

**Step 1: Clone CodeCommit Repository**

```bash
# Get repository URL from stack outputs
REPO_URL=$(aws cloudformation describe-stacks \
  --stack-name SalesAgentRuntimeStack-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CodeCommitRepositoryUrl`].OutputValue' \
  --output text)

# Clone repository
git clone $REPO_URL sales-agent-prod
cd sales-agent-prod
```

**Step 2: Push Initial Code**

```bash
# Copy project files
cp -r ../agentcore-cdk-infrastructure/* .

# Add and commit
git add .
git commit -m "feat(init): initial project setup"

# Push to trigger pipeline
git push origin main
```

**Step 3: Monitor Pipeline**

```bash
# Watch pipeline execution
aws codepipeline get-pipeline-state --name SalesAgentPipeline-prod

# Or use AWS Console
# Navigate to: CodePipeline → Pipelines → SalesAgentPipeline-prod
```

### Pipeline Stages

**1. Source Stage**:
- Monitors main branch
- Triggers on commit
- Outputs source artifact

**2. Build Stage**:
- Installs dependencies with uv
- Runs unit tests
- Builds ARM64 Docker image
- Pushes to ECR
- Generates deployment artifact

**3. Deploy Stage**:
- Blue/green deployment
- Health checks (300s grace period)
- Traffic shift
- Rollback on failure

### Build Customization

Edit `buildspec.yml` to customize build process:

```yaml
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
      - COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=${COMMIT_HASH:=latest}
  
  build:
    commands:
      - echo Build started on `date`
      - echo Running unit tests...
      - pip install uv && uv pip install --system pytest
      - uv pip install --system -r requirements.txt
      - pytest tests/unit/ --junitxml=test-results.xml
      - echo Building Docker image for ARM64...
      - docker buildx build --platform linux/arm64 -t $ECR_REPOSITORY:$IMAGE_TAG runtime/
      - docker tag $ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
  
  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing Docker image...
      - docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
      - printf '[{"name":"runtime","imageUri":"%s"}]' $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
  
reports:
  test-results:
    files:
      - test-results.xml
    file-format: JUNITXML
```

## Rollback Procedures

### Automatic Rollback

CodeDeploy automatically rolls back on:
- Health check failures
- CloudWatch alarm triggers
- Deployment timeout

### Manual Rollback

**Option 1: Redeploy Previous Version**

```bash
# Get previous image tag
aws ecr describe-images \
  --repository-name sales-agent-prod \
  --query 'sort_by(imageDetails,& imagePushedAt)[-2].imageTags[0]' \
  --output text

# Update task definition with previous image
# Trigger new deployment
```

**Option 2: CloudFormation Stack Rollback**

```bash
# Rollback to previous stack version
aws cloudformation cancel-update-stack \
  --stack-name SalesAgentRuntimeStack-prod
```

**Option 3: Parameter Rollback**

```bash
# Get parameter history
aws ssm get-parameter-history \
  --name /sales-agent/prod/item_table

# Restore previous value
aws ssm put-parameter \
  --name /sales-agent/prod/item_table \
  --value "previous-value" \
  --overwrite
```

## Production Checklist

### Pre-Deployment

- [ ] All tests passing (unit, property, integration)
- [ ] Code reviewed and approved
- [ ] Security scan completed
- [ ] Performance testing completed
- [ ] Documentation updated
- [ ] Rollback plan documented
- [ ] Stakeholders notified

### Deployment

- [ ] Backup current configuration
- [ ] Deploy to staging first
- [ ] Verify staging deployment
- [ ] Schedule maintenance window
- [ ] Deploy to production
- [ ] Monitor deployment progress
- [ ] Verify health checks passing

### Post-Deployment

- [ ] Smoke tests completed
- [ ] Monitoring dashboards reviewed
- [ ] No alarms triggered
- [ ] Logs reviewed for errors
- [ ] Performance metrics within SLA
- [ ] Stakeholders notified of completion
- [ ] Documentation updated with deployment notes

### Production Monitoring

**First 24 Hours**:
- Monitor CloudWatch dashboards every hour
- Review logs for errors
- Check alarm status
- Monitor latency and error rates
- Be ready for quick rollback

**Ongoing**:
- Daily log review
- Weekly performance analysis
- Monthly cost optimization review
- Quarterly security audit

---

## Additional Resources

- [README.md](../README.md) - Getting started guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture diagrams
- [API.md](API.md) - API documentation
- [AWS CDK Best Practices](https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
