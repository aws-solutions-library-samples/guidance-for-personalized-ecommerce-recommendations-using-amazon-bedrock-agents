#!/bin/bash
set -euo pipefail

# Ensure we run from the script's directory (where pyproject.toml lives)
cd "$(dirname "${BASH_SOURCE[0]}")"

# Usage: ./deploy.sh \
#   --aoss-endpoint <endpoint> \
#   [--env <environment>] \
#   [--memory-id <id>] \
#   [--memory-mode create|external] \
#   [--item-table <name>] \
#   [--user-table <name>] \
#   [--recommender-arn <arn>] \
#   [--model-id <model-id>] \
#   [--network-mode PUBLIC|PRIVATE] \
#   [--subnets <comma-separated>] \
#   [--security-groups <comma-separated>] \
#   [--aoss-data-policy-name <policy-name>] \
#   [--region <region>] \
#   [--profile <profile>]

AOSS_ENDPOINT=""
ENV_NAME="production"
MEMORY_ID=""
MEMORY_MODE=""
ITEM_TABLE=""
USER_TABLE=""
RECOMMENDER_ARN=""
MODEL_ID=""
NETWORK_MODE=""
SUBNETS=""
SECURITY_GROUPS=""
REGION=""
PROFILE=""
AOSS_DATA_POLICY_NAME=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --aoss-endpoint)
            AOSS_ENDPOINT="$2"
            shift 2
            ;;
        --env)
            ENV_NAME="$2"
            shift 2
            ;;
        --memory-id)
            MEMORY_ID="$2"
            shift 2
            ;;
        --memory-mode)
            MEMORY_MODE="$2"
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
        --model-id)
            MODEL_ID="$2"
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
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --aoss-data-policy-name)
            AOSS_DATA_POLICY_NAME="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            echo "Usage: ./deploy.sh --aoss-endpoint <endpoint> [--env <environment>] [--memory-id <id>] [--memory-mode create|external] [--item-table <name>] [--user-table <name>] [--recommender-arn <arn>] [--network-mode PUBLIC|PRIVATE] [--subnets <ids>] [--security-groups <ids>] [--region <region>]"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$AOSS_ENDPOINT" ]]; then
    echo "Error: --aoss-endpoint is required"
    exit 1
fi

if [[ -z "$RECOMMENDER_ARN" ]]; then
    echo "Error: --recommender-arn is required"
    exit 1
fi

if [[ -z "$PROFILE" ]]; then
    echo "Error: --profile is required"
    exit 1
fi

# Resolve memory mode
if [[ -n "$MEMORY_MODE" ]]; then
    : # Use provided value
elif [[ -n "$MEMORY_ID" ]]; then
    MEMORY_MODE="external"
else
    MEMORY_MODE="create"
fi

# Validate memory mode + memory ID combination
if [[ "$MEMORY_MODE" == "external" && -z "$MEMORY_ID" ]]; then
    echo "Error: --memory-id is required when --memory-mode is 'external'"
    exit 1
fi

# Export AWS_PROFILE early so all subprocesses (cdk, uv run, python3) inherit it
export AWS_PROFILE="$PROFILE"

STACK_NAME="AgentCoreStack-${ENV_NAME}"
OUTPUTS_FILE="cdk-outputs-${ENV_NAME}.json"

# Build CDK context args
CDK_CONTEXT_ARGS="--context aoss-endpoint=$AOSS_ENDPOINT --context env-name=$ENV_NAME --context memory-mode=$MEMORY_MODE"

if [[ -n "$MEMORY_ID" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context memory-id=$MEMORY_ID"
fi

if [[ -n "$ITEM_TABLE" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context item-table-name=$ITEM_TABLE"
fi

if [[ -n "$USER_TABLE" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context user-table-name=$USER_TABLE"
fi

if [[ -n "$RECOMMENDER_ARN" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context recommender-arn=$RECOMMENDER_ARN"
fi

if [[ -n "$MODEL_ID" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context model-id=$MODEL_ID"
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

if [[ -n "$AOSS_DATA_POLICY_NAME" ]]; then
    CDK_CONTEXT_ARGS="$CDK_CONTEXT_ARGS --context aoss-data-policy-name=$AOSS_DATA_POLICY_NAME"
fi

REGION_ARGS=""
if [[ -n "$REGION" ]]; then
    REGION_ARGS="--region $REGION"
fi

PROFILE_ARGS=""
if [[ -n "$PROFILE" ]]; then
    PROFILE_ARGS="--profile $PROFILE"
fi

# Ensure cdk package is importable from the project root
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"

# Deploy CDK stack
echo "Deploying ${STACK_NAME}..."
echo "  Environment: $ENV_NAME"
echo "  AOSS Endpoint: $AOSS_ENDPOINT"
if ! cdk deploy "$STACK_NAME" \
    --app "uv run python3 cdk/app.py" \
    --outputs-file "$OUTPUTS_FILE" \
    --require-approval never \
    $CDK_CONTEXT_ARGS \
    $REGION_ARGS \
    $PROFILE_ARGS; then
    echo "Error: CDK deployment failed"
    exit 1
fi

# Extract outputs from environment-specific cdk-outputs file
echo "Extracting deployment outputs..."
RUNTIME_ARN=$(uv run python3 -c "import json; data=json.load(open('${OUTPUTS_FILE}')); print(data['${STACK_NAME}']['RuntimeArn'])")
ECR_URI=$(uv run python3 -c "import json; data=json.load(open('${OUTPUTS_FILE}')); print(data['${STACK_NAME}']['EcrRepositoryUri'])")

# Print deployment summary
echo ""
echo "========================================="
echo "  Deployment Complete (${ENV_NAME})"
echo "========================================="
echo "  Runtime ARN:  $RUNTIME_ARN"
echo "  ECR URI:      $ECR_URI"
echo ""
echo "  Test with the CLI:"
echo "    uv run python3 -m cli --stack-name ${STACK_NAME} invoke -m \"search for red shoes\""
echo ""
echo "  Or start an interactive chat:"
echo "    uv run python3 -m cli --stack-name ${STACK_NAME} chat"
echo ""
if [[ -z "$AOSS_DATA_POLICY_NAME" ]]; then
    # Look up data access policy name for the collection
    DETECTED_POLICY=""
    DETECTED_POLICY=$(uv run python3 -c "
import boto3, json
session = boto3.Session()
client = session.client('opensearchserverless')
# Resolve collection ID to collection name
cols = client.batch_get_collection(ids=['${AOSS_ENDPOINT}'])
col_name = cols['collectionDetails'][0]['name'] if cols.get('collectionDetails') else None
if not col_name:
    raise SystemExit(1)
# Search data access policies for one referencing this collection name
resp = client.list_access_policies(type='data', maxResults=100)
for p in resp.get('accessPolicySummaries', []):
    detail = client.get_access_policy(type='data', name=p['name'])
    policy = detail['accessPolicyDetail']['policy']
    body = json.loads(policy) if isinstance(policy, str) else policy
    rules = body if isinstance(body, list) else [body]
    for rule in rules:
        for res in rule.get('Rules', []):
            for r in res.get('Resource', []):
                if col_name in r:
                    print(p['name'])
                    raise SystemExit(0)
" 2>/dev/null) || true

    echo "  ⚠️  WARNING: --aoss-data-policy-name was not provided."
    echo "  The execution role for this environment will NOT be automatically"
    echo "  added to the OpenSearch Serverless data access policy."
    echo "  You must manually add the role to the AOSS data access policy,"
    echo "  or the agent will fail to query the product search index."
    echo ""
    if [[ -n "$DETECTED_POLICY" ]]; then
        echo "  Detected data access policy for collection ${AOSS_ENDPOINT}: ${DETECTED_POLICY}"
        echo ""
        echo "  To automate this, re-deploy with:"
        echo "    ./deploy.sh ... --aoss-data-policy-name ${DETECTED_POLICY}"
    else
        echo "  To automate this, re-deploy with:"
        echo "    ./deploy.sh ... --aoss-data-policy-name <policy-name>"
    fi
    echo ""
fi
echo "========================================="
