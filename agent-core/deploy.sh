#!/bin/bash
set -euo pipefail

# Usage: ./deploy.sh \
#   --aoss-endpoint <endpoint> \
#   [--item-table <name>] \
#   [--user-table <name>] \
#   [--recommender-arn <arn>] \
#   [--network-mode PUBLIC|PRIVATE] \
#   [--subnets <comma-separated>] \
#   [--security-groups <comma-separated>] \
#   [--region <region>]

AOSS_ENDPOINT=""
ITEM_TABLE=""
USER_TABLE=""
RECOMMENDER_ARN=""
NETWORK_MODE=""
SUBNETS=""
SECURITY_GROUPS=""
REGION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --aoss-endpoint)
            AOSS_ENDPOINT="$2"
            shift 2
            ;;
        --item-table)
            ITEM_TABLE="$2"
            shift 2
            ;;
        --user-table)
            USER_TABLE="$2"
            shift 2
            ;;
        --recommender-arn)
            RECOMMENDER_ARN="$2"
            shift 2
            ;;
        --network-mode)
            NETWORK_MODE="$2"
            shift 2
            ;;
        --subnets)
            SUBNETS="$2"
            shift 2
            ;;
        --security-groups)
            SECURITY_GROUPS="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            echo "Usage: ./deploy.sh --aoss-endpoint <endpoint> [--item-table <name>] [--user-table <name>] [--recommender-arn <arn>] [--network-mode PUBLIC|PRIVATE] [--subnets <ids>] [--security-groups <ids>] [--region <region>]"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$AOSS_ENDPOINT" ]]; then
    echo "Error: --aoss-endpoint is required"
    echo "Usage: ./deploy.sh --aoss-endpoint <endpoint> [--item-table <name>] [--user-table <name>] [--recommender-arn <arn>] [--network-mode PUBLIC|PRIVATE] [--subnets <ids>] [--security-groups <ids>] [--region <region>]"
    exit 1
fi

# Build CDK context args
CDK_CONTEXT_ARGS="--context aoss-endpoint=$AOSS_ENDPOINT"

if [[ -n "$ITEM_TABLE" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context item-table-name=$ITEM_TABLE"
fi

if [[ -n "$USER_TABLE" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context user-table-name=$USER_TABLE"
fi

if [[ -n "$RECOMMENDER_ARN" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context recommender-arn=$RECOMMENDER_ARN"
fi

if [[ -n "$NETWORK_MODE" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context network-mode=$NETWORK_MODE"
fi

if [[ -n "$SUBNETS" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context subnets=$SUBNETS"
fi

if [[ -n "$SECURITY_GROUPS" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context security-groups=$SECURITY_GROUPS"
fi

REGION_ARGS=""
if [[ -n "$REGION" ]]; then
    REGION_ARGS="--region $REGION"
fi

# Deploy CDK stack
echo "Deploying AgentCoreStack..."
echo "  AOSS Endpoint: $AOSS_ENDPOINT"
if ! cdk deploy AgentCoreStack \
    --app "python3 cdk/app.py" \
    --outputs-file cdk-outputs.json \
    --require-approval never \
    $CDK_CONTEXT_ARGS \
    $REGION_ARGS; then
    echo "Error: CDK deployment failed"
    exit 1
fi

# Extract outputs from cdk-outputs.json
echo "Extracting deployment outputs..."
RUNTIME_ARN=$(python3 -c "import json; data=json.load(open('cdk-outputs.json')); print(data['AgentCoreStack']['RuntimeArn'])")
ECR_URI=$(python3 -c "import json; data=json.load(open('cdk-outputs.json')); print(data['AgentCoreStack']['EcrRepositoryUri'])")

# Print deployment summary
echo ""
echo "========================================="
echo "  Deployment Complete"
echo "========================================="
echo "  Runtime ARN:  $RUNTIME_ARN"
echo "  ECR URI:      $ECR_URI"
echo ""
echo "  Test invoke command:"
echo "    aws bedrock-agent-runtime invoke-agent \\"
echo "      --agent-runtime-arn $RUNTIME_ARN \\"
echo "      --payload '{\"prompt\": \"search for red shoes\"}'"
echo ""
echo "  NOTE: For subsequent image updates, rebuild and push to ECR,"
echo "  then call update_agent_runtime to redeploy the latest image."
echo "========================================="