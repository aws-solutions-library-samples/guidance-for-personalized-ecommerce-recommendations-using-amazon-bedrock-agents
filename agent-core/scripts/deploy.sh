#!/bin/bash

# Deployment script for AgentCore CDK Infrastructure
# This script orchestrates CDK deployment with parameter validation and error handling

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
STAGE=""
VPC_ID=""
DESTROY=false

# Function to display usage information
show_help() {
    cat << EOF
Usage: ./deploy.sh --stage STAGE [OPTIONS]

Deploy or destroy the AgentCore CDK infrastructure stack.

Required Arguments:
  --stage STAGE         Stage name for deployment (e.g., dev, staging, prod)
                        Must be alphanumeric with hyphens and underscores

Optional Arguments:
  --vpc-id VPC_ID       Existing VPC ID to use for deployment
                        If not provided, a new VPC will be created
  --destroy             Tear down the stack instead of deploying
  --help                Display this help message and exit

Examples:
  # Deploy to dev stage with new VPC
  ./deploy.sh --stage dev

  # Deploy to prod stage with existing VPC
  ./deploy.sh --stage prod --vpc-id vpc-0123456789abcdef0

  # Destroy dev stage stack
  ./deploy.sh --stage dev --destroy

Requirements:
  - AWS CLI configured with valid credentials
  - AWS CDK CLI installed (npm install -g aws-cdk)
  - Python 3.13+ with required dependencies installed

EOF
}

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to validate stage name format
validate_stage_name() {
    local stage=$1
    if [[ ! $stage =~ ^[a-zA-Z0-9_-]+$ ]]; then
        print_error "Invalid stage name: $stage"
        print_error "Stage name must be alphanumeric with hyphens and underscores only"
        exit 1
    fi
}

# Function to build and push placeholder image to ECR
upload_placeholder_image() {
    local stage=$1
    local account=$2
    local region=$3
    
    print_info "Checking if placeholder image is needed..."
    
    # ECR repository name
    local ecr_repo="sales-agent-runtime-$stage"
    local ecr_uri="$account.dkr.ecr.$region.amazonaws.com/$ecr_repo"
    
    # Check if ECR repository exists
    if ! aws ecr describe-repositories --repository-names "$ecr_repo" --region "$region" &>/dev/null; then
        print_info "ECR repository does not exist yet, will be created by CDK"
        return 0
    fi
    
    # Check if repository has any images
    local image_count=$(aws ecr list-images --repository-name "$ecr_repo" --region "$region" --query 'length(imageIds)' --output text 2>/dev/null || echo "0")
    
    if [ "$image_count" -gt 0 ]; then
        print_info "ECR repository already has images, skipping placeholder upload"
        return 0
    fi
    
    print_info "ECR repository is empty, uploading placeholder image..."
    
    # Check if Docker is available
    if ! command -v docker &>/dev/null; then
        print_warning "Docker is not installed, skipping placeholder image upload"
        print_warning "You may need to manually push an image to ECR before ECS can start"
        return 0
    fi
    
    # Check if placeholder Dockerfile exists
    if [ ! -f "runtime/Dockerfile.placeholder" ]; then
        print_warning "Placeholder Dockerfile not found at runtime/Dockerfile.placeholder"
        print_warning "Skipping placeholder image upload"
        return 0
    fi
    
    # Authenticate Docker to ECR
    print_info "Authenticating Docker to ECR..."
    if ! aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$account.dkr.ecr.$region.amazonaws.com" 2>/dev/null; then
        print_warning "Failed to authenticate Docker to ECR"
        print_warning "Skipping placeholder image upload"
        return 0
    fi
    
    # Build placeholder image
    print_info "Building placeholder image..."
    if ! docker build --platform linux/arm64 -t "$ecr_uri:latest" -f runtime/Dockerfile.placeholder runtime/ 2>&1 | tail -5; then
        print_warning "Failed to build placeholder image"
        print_warning "Skipping placeholder image upload"
        return 0
    fi
    
    # Push placeholder image
    print_info "Pushing placeholder image to ECR..."
    if docker push "$ecr_uri:latest" 2>&1 | tail -5; then
        print_info "Placeholder image uploaded successfully"
    else
        print_warning "Failed to push placeholder image to ECR"
        print_warning "ECS service may fail to start until a valid image is pushed"
    fi
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --stage)
            STAGE="$2"
            shift 2
            ;;
        --vpc-id)
            VPC_ID="$2"
            shift 2
            ;;
        --destroy)
            DESTROY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$STAGE" ]; then
    print_error "Missing required argument: --stage"
    echo ""
    show_help
    exit 1
fi

# Validate stage name format
validate_stage_name "$STAGE"

print_info "Starting deployment process for stage: $STAGE"

# Validate AWS credentials
print_info "Validating AWS credentials..."
if ! aws sts get-caller-identity &>/dev/null; then
    print_error "AWS credentials are not configured or invalid"
    print_error "Please configure AWS credentials using one of the following methods:"
    print_error "  1. Run 'aws configure' to set up credentials"
    print_error "  2. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
    print_error "  3. Use an IAM role if running on EC2 or ECS"
    exit 1
fi

# Get AWS account and region information
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
print_info "Using AWS Account: $AWS_ACCOUNT"
print_info "Using AWS Region: $AWS_REGION"

# Check if CDK is bootstrapped
print_info "Checking CDK bootstrap status..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$AWS_REGION" &>/dev/null; then
    print_warning "CDK is not bootstrapped in this account/region"
    print_info "Running CDK bootstrap..."
    if ! (cd cdk && cdk bootstrap "aws://$AWS_ACCOUNT/$AWS_REGION"); then
        print_error "CDK bootstrap failed"
        exit 1
    fi
    print_info "CDK bootstrap completed successfully"
else
    print_info "CDK is already bootstrapped"
fi

# Handle destroy operation
if [ "$DESTROY" = true ]; then
    print_warning "Destroying stack for stage: $STAGE"
    print_warning "This will delete all resources in the stack"
    
    STACK_NAME="SalesAgentRuntimeStack-$STAGE"
    
    # Check if stack exists
    if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &>/dev/null; then
        print_warning "Stack $STACK_NAME does not exist, nothing to destroy"
        exit 0
    fi
    
    # Destroy the stack
    print_info "Running cdk destroy..."
    if (cd cdk && cdk destroy --force --context stage="$STAGE"); then
        print_info "Stack destroyed successfully"
        exit 0
    else
        print_error "Stack destruction failed"
        exit 1
    fi
fi

# Synthesize CloudFormation templates
print_info "Synthesizing CloudFormation templates..."
if ! (cd cdk && cdk synth --context stage="$STAGE"); then
    print_error "CDK synthesis failed"
    print_error "Please check your CDK code for errors"
    exit 1
fi
print_info "CloudFormation templates synthesized successfully"

# Deploy the stack
print_info "Deploying stack for stage: $STAGE"

# Build CDK deploy command
CDK_DEPLOY_CMD="cdk deploy --context stage=\"$STAGE\" --require-approval never"

# Add VPC ID context if provided
if [ -n "$VPC_ID" ]; then
    print_info "Using existing VPC: $VPC_ID"
    CDK_DEPLOY_CMD="$CDK_DEPLOY_CMD --context vpcId=\"$VPC_ID\""
else
    print_info "A new VPC will be created"
fi

# Execute deployment
print_info "Running cdk deploy..."
if (cd cdk && eval "$CDK_DEPLOY_CMD"); then
    print_info "Deployment completed successfully"
    
    # Upload placeholder image to ECR if needed (after ECR repository is created)
    upload_placeholder_image "$STAGE" "$AWS_ACCOUNT" "$AWS_REGION"
    
    # Display stack outputs
    STACK_NAME="SalesAgentRuntimeStack-$STAGE"
    print_info "Stack outputs:"
    echo ""
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo ""
    print_info "Deployment complete for stage: $STAGE"
    print_info "You can now use the CLI tool to manage the runtime:"
    print_info "  python cli/sales_agent_cli.py --stage $STAGE status"
    
    exit 0
else
    print_error "Deployment failed"
    print_error "Check the CloudFormation console for detailed error messages:"
    print_error "  https://console.aws.amazon.com/cloudformation"
    
    # Try to get recent stack events
    STACK_NAME="SalesAgentRuntimeStack-$STAGE"
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &>/dev/null; then
        print_error "Recent stack events:"
        aws cloudformation describe-stack-events \
            --stack-name "$STACK_NAME" \
            --region "$AWS_REGION" \
            --max-items 10 \
            --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[Timestamp,ResourceType,ResourceStatus,ResourceStatusReason]' \
            --output table
    fi
    
    exit 1
fi
