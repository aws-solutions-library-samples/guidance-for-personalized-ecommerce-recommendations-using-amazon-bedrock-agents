#!/bin/bash

# Bootstrap Deployment Script for AgentCore CDK Infrastructure
# This script implements the two-phase bootstrap deployment workflow

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Required arguments
STAGE=""
ITEM_TABLE=""
USER_TABLE=""
AOSS_ENDPOINT=""
PERSONALIZE_ARN=""

# Optional arguments
VPC_ID=""
DESTROY=false

# Function to display usage information
show_help() {
    cat << EOF
Usage: ./deploy_bootstrap.sh --stage STAGE --item-table TABLE --user-table TABLE \\
                              --aoss-endpoint URL --personalize-arn ARN [OPTIONS]

Bootstrap deployment for AgentCore Sales Agent infrastructure.

This script implements a two-phase deployment:
  Phase 1: Deploy BootstrapStack (CodeCommit + CodePipeline)
  Phase 2: Commit code to CodeCommit
  Phase 3: Monitor pipeline execution
  Phase 4: Update Memory ID in Parameter Store
  Phase 5: Verify deployment

Required Arguments:
  --stage STAGE                 Stage name (e.g., dev, staging, prod)
  --item-table TABLE            DynamoDB items table name
  --user-table TABLE            DynamoDB users table name
  --aoss-endpoint URL           OpenSearch Serverless endpoint
  --personalize-arn ARN         Personalize recommender ARN

Optional Arguments:
  --vpc-id VPC_ID              Existing VPC ID (creates new VPC if not provided)
  --destroy                    Tear down all stacks
  --help                       Display this help message

Examples:
  # Deploy to dev stage
  ./deploy_bootstrap.sh --stage dev \\
    --item-table my-items \\
    --user-table my-users \\
    --aoss-endpoint https://abc123.us-east-1.aoss.amazonaws.com \\
    --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-rec

  # Destroy dev stage
  ./deploy_bootstrap.sh --stage dev --destroy

EOF
}

# Print functions
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_phase() { echo -e "${BLUE}[PHASE]${NC} $1"; }

# Validate stage name
validate_stage_name() {
    if [[ ! $1 =~ ^[a-zA-Z0-9_-]+$ ]]; then
        print_error "Invalid stage name: $1"
        print_error "Must be alphanumeric with hyphens/underscores only"
        exit 1
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --stage) STAGE="$2"; shift 2 ;;
        --item-table) ITEM_TABLE="$2"; shift 2 ;;
        --user-table) USER_TABLE="$2"; shift 2 ;;
        --aoss-endpoint) AOSS_ENDPOINT="$2"; shift 2 ;;
        --personalize-arn) PERSONALIZE_ARN="$2"; shift 2 ;;
        --vpc-id) VPC_ID="$2"; shift 2 ;;
        --destroy) DESTROY=true; shift ;;
        --help) show_help; exit 0 ;;
        *) print_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# Validate required arguments
if [ -z "$STAGE" ]; then
    print_error "Missing required argument: --stage"
    show_help
    exit 1
fi

if [ "$DESTROY" = false ]; then
    if [ -z "$ITEM_TABLE" ] || [ -z "$USER_TABLE" ] || [ -z "$AOSS_ENDPOINT" ] || [ -z "$PERSONALIZE_ARN" ]; then
        print_error "Missing required arguments for deployment"
        show_help
        exit 1
    fi
fi

validate_stage_name "$STAGE"

print_info "Starting bootstrap deployment for stage: $STAGE"

# Validate AWS credentials
print_info "Validating AWS credentials..."
if ! aws sts get-caller-identity &>/dev/null; then
    print_error "AWS credentials not configured"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
print_info "AWS Account: $AWS_ACCOUNT, Region: $AWS_REGION"

# Check CDK bootstrap
print_info "Checking CDK bootstrap..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$AWS_REGION" &>/dev/null; then
    print_info "Bootstrapping CDK..."
    (cd cdk && cdk bootstrap "aws://$AWS_ACCOUNT/$AWS_REGION")
fi

# Handle destroy
if [ "$DESTROY" = true ]; then
    print_warning "Destroying stacks for stage: $STAGE"
    
    (cd cdk && cdk destroy RuntimeStack-$STAGE --force --context stage="$STAGE" || true)
    (cd cdk && cdk destroy InfrastructureStack-$STAGE --force --context stage="$STAGE" || true)
    (cd cdk && cdk destroy BootstrapStack-$STAGE --force --context stage="$STAGE" || true)
    
    # Delete Parameter Store parameters
    print_info "Deleting Parameter Store parameters..."
    aws ssm delete-parameters --names $(aws ssm get-parameters-by-path --path "/sales-agent/$STAGE/" --query "Parameters[].Name" --output text) 2>/dev/null || true
    
    print_info "Destroy complete"
    exit 0
fi

# Phase 1: Deploy BootstrapStack
print_phase "Phase 1: Deploying BootstrapStack"

CDK_CMD="cdk deploy BootstrapStack-$STAGE --require-approval never"
CDK_CMD="$CDK_CMD --context bootstrap=true"
CDK_CMD="$CDK_CMD --context stage=\"$STAGE\""
CDK_CMD="$CDK_CMD --context itemTable=\"$ITEM_TABLE\""
CDK_CMD="$CDK_CMD --context userTable=\"$USER_TABLE\""
CDK_CMD="$CDK_CMD --context aossEndpoint=\"$AOSS_ENDPOINT\""
CDK_CMD="$CDK_CMD --context personalizeArn=\"$PERSONALIZE_ARN\""
[ -n "$VPC_ID" ] && CDK_CMD="$CDK_CMD --context vpcId=\"$VPC_ID\""

if ! (cd cdk && eval "$CDK_CMD"); then
    print_error "BootstrapStack deployment failed"
    exit 1
fi

# Get stack outputs
REPO_URL=$(aws cloudformation describe-stacks --stack-name "BootstrapStack-$STAGE" --query "Stacks[0].Outputs[?OutputKey=='RepositoryUrl'].OutputValue" --output text)
PIPELINE_NAME=$(aws cloudformation describe-stacks --stack-name "BootstrapStack-$STAGE" --query "Stacks[0].Outputs[?OutputKey=='PipelineName'].OutputValue" --output text)

print_info "Repository URL: $REPO_URL"
print_info "Pipeline Name: $PIPELINE_NAME"

# Phase 2: Commit code to CodeCommit
print_phase "Phase 2: Committing code to CodeCommit"

if [ ! -d ".git" ]; then
    print_info "Initializing git repository..."
    git init
    git add .
    git commit -m "Initial deployment for stage $STAGE"
fi

print_info "Configuring CodeCommit remote..."
git remote remove codecommit-$STAGE 2>/dev/null || true
git remote add codecommit-$STAGE "$REPO_URL"

print_info "Pushing code to CodeCommit..."
git push codecommit-$STAGE main --force

COMMIT_HASH=$(git rev-parse --short HEAD)
print_info "Pushed commit: $COMMIT_HASH"

# Phase 3: Monitor pipeline execution
print_phase "Phase 3: Monitoring pipeline execution"

print_info "Waiting for pipeline to start..."
sleep 10

EXECUTION_ID=""
for i in {1..30}; do
    EXECUTION_ID=$(aws codepipeline list-pipeline-executions --pipeline-name "$PIPELINE_NAME" --max-items 1 --query "pipelineExecutionSummaries[0].pipelineExecutionId" --output text 2>/dev/null || echo "")
    if [ -n "$EXECUTION_ID" ] && [ "$EXECUTION_ID" != "None" ]; then
        break
    fi
    sleep 2
done

if [ -z "$EXECUTION_ID" ] || [ "$EXECUTION_ID" = "None" ]; then
    print_error "Pipeline did not start"
    exit 1
fi

print_info "Pipeline execution ID: $EXECUTION_ID"
print_info "Monitoring pipeline progress..."

while true; do
    STATUS=$(aws codepipeline get-pipeline-execution --pipeline-name "$PIPELINE_NAME" --pipeline-execution-id "$EXECUTION_ID" --query "pipelineExecution.status" --output text)
    
    case $STATUS in
        "Succeeded")
            print_info "Pipeline completed successfully!"
            break
            ;;
        "Failed"|"Stopped"|"Stopping")
            print_error "Pipeline failed with status: $STATUS"
            exit 1
            ;;
        "InProgress")
            echo -n "."
            sleep 10
            ;;
        *)
            print_warning "Unknown pipeline status: $STATUS"
            sleep 10
            ;;
    esac
done

# Phase 4: Update Memory ID
print_phase "Phase 4: Updating Memory ID in Parameter Store"

MEMORY_ID=$(aws cloudformation describe-stacks --stack-name "InfrastructureStack-$STAGE" --query "Stacks[0].Outputs[?OutputKey=='MemoryId'].OutputValue" --output text 2>/dev/null || echo "")

if [ -n "$MEMORY_ID" ] && [ "$MEMORY_ID" != "None" ]; then
    print_info "Memory ID: $MEMORY_ID"
    aws ssm put-parameter --name "/sales-agent/$STAGE/memory_id" --value "$MEMORY_ID" --type String --overwrite
    print_info "Memory ID updated in Parameter Store"
else
    print_warning "Could not retrieve Memory ID"
fi

# Phase 5: Display outputs and verification prompt
print_phase "Phase 5: Deployment Complete"

echo ""
print_info "Stack Outputs:"
aws cloudformation describe-stacks --stack-name "RuntimeStack-$STAGE" --query "Stacks[0].Outputs" --output table 2>/dev/null || true

echo ""
print_info "Test the deployment with:"
print_info "  python cli/sales_agent_cli.py --stage $STAGE invoke --message 'test'"

echo ""
read -p "Press Enter to confirm deployment is working..."

print_info "Bootstrap deployment complete for stage: $STAGE"
