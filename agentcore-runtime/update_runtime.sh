#!/bin/bash
set -euo pipefail

# Usage: ./update_runtime.sh --stack-name <stack-name> [--auto-update-hosting] [--region <region>] [--profile <profile>]
#
# Uploads new source code to S3, triggers CodeBuild to build a new Docker image,
# and optionally updates the AgentCore Runtime to pick up the new image.

STACK_NAME=""
AUTO_UPDATE_HOSTING=""
REGION=""
PROFILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        --auto-update-hosting)
            AUTO_UPDATE_HOSTING="true"
            shift
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            echo "Usage: ./update_runtime.sh --stack-name <stack-name> [--auto-update-hosting] [--region <region>] [--profile <profile>]"
            exit 1
            ;;
    esac
done

if [[ -z "$STACK_NAME" ]]; then
    echo "Error: --stack-name is required"
    exit 1
fi

AWS_ARGS=""
if [[ -n "$REGION" ]]; then
    AWS_ARGS="$AWS_ARGS --region $REGION"
fi
if [[ -n "$PROFILE" ]]; then
    AWS_ARGS="$AWS_ARGS --profile $PROFILE"
    export AWS_PROFILE="$PROFILE"
fi

# --- 1. Fetch stack outputs ---
echo "Checking stack ${STACK_NAME}..."
STACK_STATUS=$(uv run aws cloudformation describe-stacks --stack-name "$STACK_NAME" $AWS_ARGS \
    --query "Stacks[0].StackStatus" --output text 2>&1) || {
    echo "❌ Error: Stack '${STACK_NAME}' not found or not accessible."
    exit 1
}

if [[ "$STACK_STATUS" != *"COMPLETE"* ]] || [[ "$STACK_STATUS" == *"DELETE"* ]]; then
    echo "❌ Error: Stack '${STACK_NAME}' is in state '${STACK_STATUS}'. Expected a *_COMPLETE status."
    echo "  Resolve the stack issue before running update."
    exit 1
fi

echo "  Stack status: $STACK_STATUS ✅"
echo ""
echo "Fetching stack outputs..."
OUTPUTS=$(uv run aws cloudformation describe-stacks --stack-name "$STACK_NAME" $AWS_ARGS \
    --query "Stacks[0].Outputs" --output json)

get_output() {
    echo "$OUTPUTS" | uv run python3 -c "
import sys, json
outputs = json.load(sys.stdin)
matches = [o['OutputValue'] for o in outputs if o['OutputKey'] == '$1']
print(matches[0] if matches else '')
"
}

ECR_URI=$(get_output "EcrRepositoryUri")
RUNTIME_ID=$(get_output "RuntimeId")
CODEBUILD_PROJECT=$(get_output "CodeBuildProjectName")

# Fallback: look up CodeBuild project from stack resources if output not available
if [[ -z "$CODEBUILD_PROJECT" ]]; then
    echo "  CodeBuildProjectName output not found, looking up from stack resources..."
    CODEBUILD_PROJECT=$(uv run aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" $AWS_ARGS \
        --query "StackResources[?ResourceType=='AWS::CodeBuild::Project'].PhysicalResourceId" \
        --output text)
fi

if [[ -z "$ECR_URI" || -z "$RUNTIME_ID" || -z "$CODEBUILD_PROJECT" ]]; then
    echo "❌ Error: Could not retrieve required stack outputs (EcrRepositoryUri, RuntimeId, CodeBuildProjectName)."
    exit 1
fi

echo "  ECR URI:          $ECR_URI"
echo "  Runtime ID:       $RUNTIME_ID"
echo "  CodeBuild Project: $CODEBUILD_PROJECT"

# --- 2. Package and upload source to S3 ---
echo ""
echo "Packaging source code..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMPDIR=$(mktemp -d)
ARCHIVE="$TMPDIR/source.zip"

# Get the S3 source bucket/key from the CodeBuild project
SOURCE_INFO=$(uv run aws codebuild batch-get-projects --names "$CODEBUILD_PROJECT" $AWS_ARGS \
    --query "projects[0].source" --output json)
S3_BUCKET=$(echo "$SOURCE_INFO" | uv run python3 -c "import sys,json; d=json.load(sys.stdin); print(d['location'].split('/')[0])")
S3_KEY=$(echo "$SOURCE_INFO" | uv run python3 -c "import sys,json; d=json.load(sys.stdin); loc=d['location']; print('/'.join(loc.split('/')[1:]))")

echo "  S3 Source: s3://$S3_BUCKET/$S3_KEY"

# Create zip of source (matching CDK asset excludes)
(cd "$SCRIPT_DIR" && zip -r "$ARCHIVE" . \
    -x ".venv/*" "__pycache__/*" "*.pyc" ".env" "cdk-outputs*.json" \
       "cdk.out/*" "tests/*" ".cdkignore" "deploy.sh" "update.sh" \
       ".hypothesis/*" ".pytest_cache/*") > /dev/null

echo "  Uploading source to S3..."
uv run aws s3 cp "$ARCHIVE" "s3://$S3_BUCKET/$S3_KEY" $AWS_ARGS > /dev/null
rm -rf "$TMPDIR"
echo "  ✅ Source uploaded"

# --- 3. Trigger CodeBuild ---
echo ""
echo "Triggering CodeBuild..."
BUILD_RESPONSE=$(uv run aws codebuild start-build --project-name "$CODEBUILD_PROJECT" $AWS_ARGS --output json)
BUILD_ID=$(echo "$BUILD_RESPONSE" | uv run python3 -c "import sys,json; print(json.load(sys.stdin)['build']['id'])")
echo "  Build ID: $BUILD_ID"

# Poll until build completes
echo "  Waiting for build to complete..."
while true; do
    sleep 15
    BUILD_STATUS=$(uv run aws codebuild batch-get-builds --ids "$BUILD_ID" $AWS_ARGS \
        --query "builds[0].buildStatus" --output text)
    case "$BUILD_STATUS" in
        SUCCEEDED)
            echo "  ✅ Build succeeded"
            break
            ;;
        FAILED|STOPPED)
            echo "  ❌ Build $BUILD_STATUS"
            echo "  Check logs: aws codebuild batch-get-builds --ids $BUILD_ID $AWS_ARGS"
            exit 1
            ;;
        *)
            echo "  ⏳ Build in progress..."
            ;;
    esac
done

# --- 4. Update hosting (or remind user) ---
echo ""
if [[ "$AUTO_UPDATE_HOSTING" == "true" ]]; then
    echo "Updating AgentCore Runtime hosting..."
    uv run python3 << PYEOF
import boto3, json

session = boto3.Session(
    ${PROFILE:+profile_name='$PROFILE',}
    ${REGION:+region_name='$REGION'}
)
client = session.client('bedrock-agentcore-control')

# Fetch current runtime config
runtime = client.get_agent_runtime(agentRuntimeId='$RUNTIME_ID')

# Build update params from current config
update_params = {
    'agentRuntimeId': '$RUNTIME_ID',
    'agentRuntimeArtifact': runtime['agentRuntimeArtifact'],
    'roleArn': runtime['roleArn'],
    'networkConfiguration': runtime['networkConfiguration'],
}

# Pass through optional fields if present
for key in ('environmentVariables', 'protocolConfiguration', 'description'):
    if key in runtime and runtime[key]:
        update_params[key] = runtime[key]

resp = client.update_agent_runtime(**update_params)
print(f"  ✅ Runtime update triggered (version: {resp.get('agentRuntimeVersion', 'unknown')})")
print(f"  The DEFAULT endpoint will point to the new version once ready.")
PYEOF
else
    echo "========================================="
    echo "  ⚠️  Image built and pushed, but hosting was NOT updated."
    echo ""
    echo "  The new image is in ECR but AgentCore is still running the old version."
    echo "  To update hosting, run:"
    echo ""
    echo "    ./update_runtime.sh --stack-name $STACK_NAME --auto-update-hosting $AWS_ARGS"
    echo "========================================="
fi

echo ""
echo "Done."
