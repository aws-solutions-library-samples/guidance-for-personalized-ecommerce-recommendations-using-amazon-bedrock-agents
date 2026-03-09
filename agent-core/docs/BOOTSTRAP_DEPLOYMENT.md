# Bootstrap Deployment Architecture

## Overview

This document explains the CodePipeline-based bootstrap deployment architecture that solves the chicken-and-egg problem in deploying containerized AgentCore applications.

## The Problem: Chicken-and-Egg Dependency

Traditional CDK deployments of containerized applications face a circular dependency:

1. **CDK needs Docker image** → The CDK stack references a Docker image that must exist in ECR
2. **ECR created by CDK** → But the ECR repository is created by the CDK deployment
3. **Local ARM64 builds required** → Users would need to build the ARM64 image locally before deployment
4. **No ARM64 hardware** → Most users don't have ARM64 machines or Docker buildx configured
5. **Missing parameters** → Required parameters (DynamoDB tables, OpenSearch endpoint, Personalize ARN) must be known before deployment

This creates an impossible situation: you can't deploy without the image, but you can't create the image repository without deploying.

## The Solution: Two-Phase Bootstrap Deployment

The bootstrap deployment approach solves this problem using CodePipeline to orchestrate the deployment in the correct order:

### Phase 1: Bootstrap Stack Deployment

The `deploy.sh` script first deploys a minimal **BootstrapStack** containing:

- **CodeCommit Repository**: Git repository for source code
- **CodePipeline**: Automated deployment pipeline
- **CodeBuild Project**: Build environment with ARM64 compute
- **S3 Artifact Bucket**: Storage for pipeline artifacts
- **IAM Roles**: Permissions for pipeline execution

**Key Point**: This stack doesn't require any Docker images or ECR repositories. It only creates the CI/CD infrastructure.

### Phase 2: Code Commit

Once the BootstrapStack is deployed, `deploy.sh`:

1. Initializes a git repository (if not already initialized)
2. Commits all source code to the local repository
3. Pushes the code to the CodeCommit repository

**Key Point**: Pushing to CodeCommit automatically triggers the CodePipeline.

### Phase 3: Pipeline Execution (Automated)

The CodePipeline automatically executes the following steps:

1. **Deploy InfrastructureStack**
   - Creates VPC, IAM roles, Parameter Store entries
   - **Creates ECR repository** (this is the key!)
   - Creates shared infrastructure resources

2. **Build Docker Image**
   - CodeBuild runs on ARM64 compute (native Graviton)
   - Builds the Docker image for linux/arm64 platform
   - **Pushes image to the ECR repository created in step 1**

3. **Deploy RuntimeStack**
   - Creates ECS/Fargate compute resources
   - References the Docker image that now exists in ECR
   - Creates AgentCore Memory and monitoring resources

**Key Point**: The pipeline creates the ECR repository BEFORE building the Docker image, solving the circular dependency.

### Phase 4: Status Tracking

While the pipeline executes, `deploy.sh`:

- Polls CodePipeline execution status
- Reports progress to the user
- Waits for pipeline to complete successfully or fail

### Phase 5: Memory Update

Once the pipeline completes successfully, `deploy.sh`:

- Retrieves the AgentCore Memory ID from stack outputs
- Updates Parameter Store with the memory ID
- Enables the runtime to access conversation history

### Phase 6: User Verification

Finally, `deploy.sh`:

- Displays all stack outputs (endpoints, URLs, etc.)
- Prompts the user to verify the service is working
- Suggests a test command: `sales-agent-cli --stage dev invoke --message "test"`

## Why This Architecture Works

### 1. No Local ARM64 Build Required

**Problem**: Most developers don't have ARM64 machines or Docker buildx configured.

**Solution**: CodeBuild runs on ARM64 compute (AMAZON_LINUX_2_ARM_3), so it builds native ARM64 images without requiring the user to have ARM64 hardware.

### 2. No Circular Dependency

**Problem**: CDK needs Docker image, but ECR is created by CDK.

**Solution**: The bootstrap stack creates the pipeline first, then the pipeline creates resources in the correct order (ECR before Docker build).

### 3. Parameter Injection

**Problem**: Required parameters must be known before deployment.

**Solution**: `deploy.sh` collects all required parameters upfront and passes them through the deployment chain via CDK context and CodeBuild environment variables.

### 4. Automated and Consistent

**Problem**: Manual builds are error-prone and environment-dependent.

**Solution**: The entire build and deployment happens in AWS with a consistent environment, eliminating "works on my machine" issues.

### 5. Idempotent

**Problem**: Re-running deployments can fail or create duplicate resources.

**Solution**: Re-running `deploy.sh` updates the existing stacks rather than failing, making deployments repeatable.

### 6. Traceable

**Problem**: Deployment failures are hard to debug.

**Solution**: Pipeline execution provides full visibility into each deployment step via the CodePipeline console.

## Trade-offs

### Costs

- **Initial Deployment Time**: First deployment takes 10-15 minutes (vs 5 minutes for direct CDK deployment)
- **AWS Service Costs**: CodePipeline and CodeBuild incur small costs per execution (~$0.01-0.05 per deployment)

### Benefits

- **No Local Dependencies**: Users don't need Docker, buildx, or ARM64 hardware
- **Automated CI/CD**: Built-in pipeline for continuous deployment from day one
- **Consistent Builds**: Same build environment for all deployments
- **Parameter Validation**: All required parameters validated before deployment starts
- **Traceable**: Full visibility into each deployment step

**Verdict**: The benefits far outweigh the costs. The additional complexity is hidden from users behind a simple `./deploy.sh` command.

## Deployment Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1: Bootstrap Stack Deployment                                 │
│                                                                      │
│  deploy.sh --stage dev \                                            │
│    --item-table items \                                             │
│    --user-table users \                                             │
│    --aoss-endpoint https://... \                                    │
│    --personalize-arn arn:aws:...                                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ BootstrapStack                                                │  │
│  │  - CodeCommit Repository                                      │  │
│  │  - CodePipeline (Source + Build stages)                       │  │
│  │  - CodeBuild Project (ARM64 compute)                          │  │
│  │  - S3 Artifact Bucket                                         │  │
│  │  - IAM Roles                                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 2: Code Commit                                                │
│                                                                      │
│  git init                                                           │
│  git add .                                                          │
│  git commit -m "Initial deployment"                                │
│  git push codecommit main                                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 3: Pipeline Execution (Automated)                             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 1: Deploy InfrastructureStack                           │  │
│  │  - VPC, IAM roles, Parameter Store                           │  │
│  │  - ECR repository ← KEY: Created before Docker build         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 2: Build Docker Image                                   │  │
│  │  - CodeBuild runs on ARM64 compute                           │  │
│  │  - Builds image for linux/arm64 platform                     │  │
│  │  - Pushes to ECR repository ← Now exists!                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 3: Deploy RuntimeStack                                  │  │
│  │  - ECS/Fargate compute                                       │  │
│  │  - References Docker image ← Now exists in ECR!              │  │
│  │  - AgentCore Memory, monitoring                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 4: Status Tracking                                            │
│                                                                      │
│  deploy.sh polls CodePipeline status                                │
│  Reports progress: Source → Build → Deploy                          │
│  Waits for completion                                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 5: Memory Update                                              │
│                                                                      │
│  Retrieve AgentCore Memory ID from stack outputs                    │
│  Update Parameter Store: /sales-agent/dev/memory_id                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 6: User Verification                                          │
│                                                                      │
│  Display stack outputs (endpoints, URLs)                            │
│  Prompt user to test: sales-agent-cli --stage dev invoke ...        │
│  Wait for user confirmation                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Usage Example

### First Deployment

```bash
./deploy.sh \
  --stage dev \
  --item-table my-items-table \
  --user-table my-users-table \
  --aoss-endpoint https://abc123.us-east-1.aoss.amazonaws.com \
  --personalize-arn arn:aws:personalize:us-east-1:123456789012:recommender/my-recommender
```

**Output:**
```
=== Phase 1: Deploying Bootstrap Stack ===
✓ BootstrapStack deployed successfully
  Repository URL: https://git-codecommit.us-east-1.amazonaws.com/v1/repos/agentcore-runtime-dev
  Pipeline Name: agentcore-pipeline-dev

=== Phase 2: Committing Code to CodeCommit ===
✓ Code committed and pushed to CodeCommit

=== Phase 3: Tracking Pipeline Execution ===
Pipeline status: InProgress (Source stage)
Pipeline status: InProgress (Build stage)
Pipeline status: Succeeded
✓ Pipeline execution completed successfully

=== Phase 4: Updating AgentCore Memory Information ===
✓ Memory ID updated in Parameter Store

=== Phase 5: Deployment Complete ===
Stack outputs:
  RuntimeEndpoint: https://abc123.execute-api.us-east-1.amazonaws.com/prod
  LogGroupName: /aws/ecs/sales-agent-dev
  VpcId: vpc-0123456789abcdef0

Please verify the service is working by invoking the runtime:
  sales-agent-cli --stage dev invoke --message 'Find me a blue dress'

Is the service working correctly? (y/n): y

✓ Deployment verified successfully!
```

### Subsequent Updates

After the initial deployment, you can update the code by simply pushing to CodeCommit:

```bash
git add .
git commit -m "Update runtime logic"
git push codecommit-dev main
```

The CodePipeline will automatically trigger and deploy the updates.

### Destroying the Deployment

```bash
./deploy.sh --stage dev --destroy
```

This will tear down all three stacks in reverse order (RuntimeStack → InfrastructureStack → BootstrapStack).

## Required Parameters

The deployment script requires the following parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--stage` | Stage name (dev, staging, prod, etc.) | `dev` |
| `--item-table` | DynamoDB table name for product items | `my-items-table` |
| `--user-table` | DynamoDB table name for user profiles | `my-users-table` |
| `--aoss-endpoint` | OpenSearch Serverless endpoint URL | `https://abc123.us-east-1.aoss.amazonaws.com` |
| `--personalize-arn` | Personalize recommender ARN | `arn:aws:personalize:us-east-1:123456789012:recommender/my-rec` |
| `--vpc-id` | (Optional) Existing VPC ID | `vpc-0123456789abcdef0` |

**Why These Parameters Are Required:**

These parameters reference external AWS resources that must exist before deployment:
- **DynamoDB tables**: Must be created and populated with product/user data
- **OpenSearch endpoint**: Must be created and configured with vector embeddings
- **Personalize recommender**: Must be trained with recommendation data

The bootstrap deployment approach ensures these parameters are validated upfront and passed through the entire deployment chain.

## Troubleshooting

### Pipeline Execution Failed

If the CodePipeline execution fails:

1. Check the CodePipeline console for detailed error messages
2. Review CodeBuild logs for build failures
3. Verify all required parameters are correct
4. Ensure IAM permissions are sufficient

**Common Issues:**
- **ECR push failed**: Check CodeBuild IAM role has `ecr:PutImage` permission
- **Stack deployment failed**: Check CloudFormation events for specific resource errors
- **Docker build failed**: Check buildspec.yml syntax and Dockerfile

### Service Verification Failed

If the service doesn't respond after deployment:

1. Check CloudWatch logs: `sales-agent-cli --stage dev logs --tail 100`
2. Verify runtime is running: `sales-agent-cli --stage dev status`
3. Check Parameter Store values: `sales-agent-cli --stage dev param list`
4. Verify VPC and security group configuration allows traffic

### Git Push Failed

If pushing to CodeCommit fails:

1. Verify CodeCommit repository was created successfully
2. Check IAM permissions for CodeCommit access
3. Verify git credentials are configured (use AWS CLI credential helper)

## Summary

The bootstrap deployment architecture solves the fundamental chicken-and-egg problem in CDK deployments of containerized applications. By using CodePipeline to orchestrate the deployment in the correct order, we eliminate the need for local ARM64 Docker builds and provide automated CI/CD infrastructure from day one.

**Key Takeaways:**

1. **No local Docker builds required** - CodeBuild handles ARM64 builds in AWS
2. **No circular dependencies** - Pipeline creates ECR before building images
3. **Automated CI/CD** - Built-in pipeline for continuous deployment
4. **Parameter validation** - All required parameters validated upfront
5. **Consistent builds** - Same environment for all deployments
6. **Traceable** - Full visibility into each deployment step

The additional complexity is hidden behind a simple `./deploy.sh` command with clear parameter requirements.
