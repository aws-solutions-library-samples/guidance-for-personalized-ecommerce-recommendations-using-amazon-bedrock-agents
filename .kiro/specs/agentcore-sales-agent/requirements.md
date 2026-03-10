# Requirements Document

## Introduction

This feature re-implements the existing Bedrock Agent-based sales assistant as a Bedrock AgentCore Runtime application using the Strands Agents SDK. The new implementation lives in the `agent-core/` working folder and preserves the same three core capabilities (product search, product comparison, personalized recommendations) while adopting the AgentCore deployment model (`agentcore dev`, `agentcore configure`, `agentcore launch`) instead of Lambda + Bedrock Agent. The Python environment is managed with `uv`. The deployment pipeline includes a CI/CD pipeline that builds ARM64 Docker images and pushes them to ECR, centralized configuration management via AWS Systems Manager Parameter Store, a single-command deploy script for end-to-end orchestration, and a Chat CLI for interactive developer testing against the deployed agent.

## Glossary

- **Sales_Agent**: The Strands-based conversational agent that orchestrates product search, comparison, and recommendation tools to assist customers
- **AgentCore_Runtime**: The Bedrock AgentCore hosting environment that runs the Sales_Agent as a managed service via `BedrockAgentCoreApp`
- **Product_Search_Tool**: A Strands tool that performs vector similarity search against OpenSearch Serverless using Titan embeddings to find products matching a text condition
- **Product_Compare_Tool**: A Strands tool that searches products by condition, retrieves user profile and history from DynamoDB, and uses Bedrock Claude to generate a comparison summary
- **Recommendation_Tool**: A Strands tool that retrieves personalized item recommendations from Amazon Personalize, enriches them with user profile and history from DynamoDB, and uses Bedrock Claude to generate a recommendation summary
- **OpenSearch_Serverless**: Amazon OpenSearch Serverless (AOSS) collection storing product embeddings for vector-based product search
- **DynamoDB**: Amazon DynamoDB tables (`item_table` and `user_table`) storing product catalog and user profile data
- **Personalize**: Amazon Personalize recommender providing personalized item recommendations per user
- **Strands_Agent**: An agent instance from the `strands-agents` SDK that uses a system prompt and a set of tools to handle conversational requests
- **Entrypoint**: The function decorated with `@app.entrypoint` in the AgentCore application that receives invocation payloads and returns results
- **UV**: A fast Python package manager used to manage the virtual environment and dependencies for the `agent-core/` project
- **CICD_Pipeline**: An AWS CodeBuild project (provisioned via CDK) that builds the ARM64 Docker image for the AgentCore Runtime and pushes it to Amazon ECR, triggered automatically by a Lambda custom resource during CDK deployment
- **ECR**: Amazon Elastic Container Registry (provisioned via CDK) used to store the ARM64 Docker image for the AgentCore Runtime
- **Parameter_Store**: AWS Systems Manager Parameter Store (provisioned via CDK) used to centrally manage configuration values (AOSS endpoint, DynamoDB table names, Personalize ARN) for the deployed agent
- **Deploy_Script**: A shell script that wraps `cdk deploy` to provision the full AgentCore Runtime stack including ECR, CodeBuild, CfnRuntime, and SSM parameters
- **Chat_CLI**: A command-line interface tool that enables developers to interactively chat with the deployed AgentCore Runtime agent in conversational sessions
- **VPC**: An Amazon Virtual Private Cloud within which the AgentCore Runtime is deployed for network isolation and access to VPC-only resources

## Requirements

### Requirement 1: Project Structure and Environment Setup

**User Story:** As a developer, I want the AgentCore sales agent project scaffolded in the `agent-core/` folder with `uv`-managed dependencies, so that I can develop and deploy the agent independently from the existing CDK stack.

#### Acceptance Criteria

1. THE Sales_Agent project SHALL reside in the `agent-core/` directory at the repository root
2. THE Sales_Agent project SHALL include a `pyproject.toml` file specifying `bedrock-agentcore`, `strands-agents`, `strands-agents-tools`, `opensearch-py`, `boto3`, and `requests-aws4auth` as dependencies
3. THE Sales_Agent project SHALL use UV as the Python package manager for virtual environment creation and dependency installation
4. THE Sales_Agent project SHALL include a `README.md` documenting setup steps, environment variable configuration, and deployment commands

### Requirement 2: AgentCore Application Entrypoint

**User Story:** As a developer, I want the agent wrapped with `BedrockAgentCoreApp` and exposed via an entrypoint function, so that the agent can be deployed and invoked through AgentCore Runtime.

#### Acceptance Criteria

1. THE Entrypoint module SHALL import `BedrockAgentCoreApp` from `bedrock_agentcore.runtime` and create an application instance
2. THE Entrypoint function SHALL be decorated with `@app.entrypoint` and defined as an async function accepting an optional `payload` parameter
3. WHEN the Entrypoint receives a payload, THE Entrypoint SHALL extract the user message from the `prompt` field of the payload
4. WHEN the Entrypoint receives a valid prompt, THE Entrypoint SHALL invoke the Strands_Agent with the user message and return the agent response in a `result` field
5. WHEN the Entrypoint module is executed directly, THE AgentCore_Runtime SHALL start the application via `app.run()`
6. IF the payload does not contain a `prompt` field, THEN THE Entrypoint SHALL use a default greeting message

### Requirement 3: Strands Agent Configuration

**User Story:** As a developer, I want the Strands Agent configured with the sales expert system prompt and all three tools, so that the agent can handle product search, comparison, and recommendation conversations.

#### Acceptance Criteria

1. THE Strands_Agent SHALL be initialized with a system prompt instructing the agent to act as a professional sales expert
2. THE Strands_Agent system prompt SHALL instruct the agent to search products based on customer conditions, compare products using user history and preferences, generate personalized recommendations, and respond in the customer's language
3. THE Strands_Agent SHALL be configured with the Product_Search_Tool, Product_Compare_Tool, and Recommendation_Tool
4. THE Strands_Agent SHALL use the Bedrock model provider with a configurable model ID defaulting to `anthropic.claude-sonnet-4-20250514`

### Requirement 4: Product Search Tool

**User Story:** As a customer, I want to search for products by describing what I need, so that I can find relevant items from the catalog.

#### Acceptance Criteria

1. WHEN the Product_Search_Tool receives a text condition, THE Product_Search_Tool SHALL generate a vector embedding using the Amazon Titan Embed Image V1 model via Bedrock Runtime
2. WHEN the embedding is generated, THE Product_Search_Tool SHALL execute a k-nearest-neighbor query against the `product-search-multimodal-index` in OpenSearch_Serverless with k=5
3. WHEN search results are returned, THE Product_Search_Tool SHALL return a list of up to 5 products, each containing item_id, score, image path, price, style, and description fields
4. THE Product_Search_Tool SHALL authenticate to OpenSearch_Serverless using AWS SigV4 credentials
5. THE Product_Search_Tool SHALL read the AOSS collection endpoint and region from environment variables `AOSS_COLLECTION_ID` and `AOSS_REGION`

### Requirement 5: Product Comparison Tool

**User Story:** As a customer, I want to compare products based on my profile and preferences, so that I can make an informed purchase decision.

#### Acceptance Criteria

1. WHEN the Product_Compare_Tool receives a user_id, condition, and preference, THE Product_Compare_Tool SHALL search for products matching the condition using the same vector search logic as the Product_Search_Tool
2. WHEN products are found, THE Product_Compare_Tool SHALL retrieve the user profile (age, gender) from the `user_table` in DynamoDB using the user_id
3. WHEN the user profile is retrieved, THE Product_Compare_Tool SHALL retrieve the user's historical visited, add-to-cart, and purchased item details from the `item_table` in DynamoDB
4. WHEN all data is gathered, THE Product_Compare_Tool SHALL construct a prompt including user demographics, history, preferences, and available items, and send the prompt to Bedrock Claude for a comparison summary
5. THE Product_Compare_Tool SHALL return both the raw product list and the LLM-generated comparison summary

### Requirement 6: Personalized Recommendation Tool

**User Story:** As a customer, I want personalized product recommendations based on my profile and shopping history, so that I can discover products tailored to my interests.

#### Acceptance Criteria

1. WHEN the Recommendation_Tool receives a user_id and preference, THE Recommendation_Tool SHALL call Amazon Personalize to retrieve up to 5 recommended items using the recommender ARN from the `RECOMMENDER_ARN` environment variable
2. IF the `RECOMMENDER_ARN` environment variable is not set, THEN THE Recommendation_Tool SHALL return a descriptive error message indicating the recommender is not configured
3. WHEN recommendations are retrieved, THE Recommendation_Tool SHALL retrieve the user profile (age, gender) from the `user_table` in DynamoDB
4. WHEN the user profile is retrieved, THE Recommendation_Tool SHALL retrieve the user's historical visited, add-to-cart, and purchased item details from the `item_table` in DynamoDB
5. WHEN all data is gathered, THE Recommendation_Tool SHALL construct a prompt including user demographics, history, preferences, and recommended items, and send the prompt to Bedrock Claude for a recommendation summary
6. THE Recommendation_Tool SHALL return both the raw recommended items list and the LLM-generated recommendation summary

### Requirement 7: Environment Configuration

**User Story:** As a developer, I want all external service endpoints and resource identifiers configurable via environment variables, so that the agent can be deployed across different environments without code changes.

#### Acceptance Criteria

1. THE Sales_Agent SHALL read the OpenSearch Serverless collection ID from the `AOSS_COLLECTION_ID` environment variable
2. THE Sales_Agent SHALL read the AWS region for OpenSearch Serverless from the `AOSS_REGION` environment variable
3. THE Sales_Agent SHALL read the Amazon Personalize recommender ARN from the `RECOMMENDER_ARN` environment variable
4. THE Sales_Agent SHALL read the DynamoDB item table name from the `ITEM_TABLE_NAME` environment variable, defaulting to `item_table`
5. THE Sales_Agent SHALL read the DynamoDB user table name from the `USER_TABLE_NAME` environment variable, defaulting to `user_table`
6. THE Sales_Agent SHALL read the Bedrock model ID from the `MODEL_ID` environment variable, defaulting to `anthropic.claude-sonnet-4-20250514`
7. THE Sales_Agent project SHALL include a `.env.example` file documenting all required and optional environment variables

### Requirement 8: Local Development and Deployment

**User Story:** As a developer, I want to run and test the agent locally using `agentcore dev` and deploy it using `agentcore launch`, so that I can iterate quickly and deploy to production.

#### Acceptance Criteria

1. THE Sales_Agent SHALL be runnable locally via the `agentcore dev` command for development and testing
2. THE Sales_Agent SHALL be testable locally via `agentcore invoke --dev '{"prompt": "search for red shoes"}'`
3. THE Sales_Agent SHALL be configurable for deployment via `agentcore configure --entrypoint agent.py --non-interactive`
4. THE Sales_Agent SHALL be deployable to AgentCore_Runtime via the `agentcore launch` command

### Requirement 9: Error Handling

**User Story:** As a developer, I want the agent to handle errors gracefully, so that failures in external services do not crash the agent.

#### Acceptance Criteria

1. IF OpenSearch_Serverless is unreachable or returns an error, THEN THE Product_Search_Tool SHALL return a descriptive error message instead of raising an unhandled exception
2. IF DynamoDB returns no results for a given user_id, THEN THE Product_Compare_Tool SHALL return a descriptive error message indicating the user was not found
3. IF DynamoDB returns no results for a given item_id, THEN THE Product_Compare_Tool SHALL return a descriptive error message indicating the item was not found
4. IF Amazon Personalize returns an error, THEN THE Recommendation_Tool SHALL return a descriptive error message indicating the recommendation service is unavailable
5. IF Bedrock Runtime returns an error during embedding generation, THEN THE Product_Search_Tool SHALL return a descriptive error message indicating the embedding service is unavailable
6. IF Bedrock Runtime returns an error during LLM invocation, THEN THE Product_Compare_Tool SHALL return a descriptive error message indicating the summarization service is unavailable

### Requirement 10: CDK Stack for AgentCore Infrastructure

**User Story:** As a developer, I want the AgentCore deployment infrastructure (ECR repository, CodeBuild project, SSM parameters) provisioned via AWS CDK, so that infrastructure is version-controlled, repeatable, and consistent with the existing CDK-based project.

#### Acceptance Criteria

1. THE CDK stack SHALL create an Amazon ECR repository for storing the ARM64 Docker image
2. THE CDK stack SHALL create an AWS CodeBuild project configured to build ARM64 Docker images from the `agent-core/` directory and push them to the ECR repository, with source uploaded as an S3 asset
3. THE CDK stack SHALL define the buildspec inline in the CodeBuild project with phases: ECR login, Docker build (ARM64 native), and Docker push
4. THE CDK stack SHALL create AWS Systems Manager Parameter Store parameters under the `/agentcore/sales-agent/` prefix for AOSS endpoint, DynamoDB table names, and Personalize ARN
5. THE CDK stack SHALL accept AOSS endpoint, DynamoDB table names, Personalize ARN, network mode, subnets, and security groups as CDK context parameters or stack properties
6. THE CDK stack SHALL include a Dockerfile in `agent-core/` that installs all Python dependencies and configures the AgentCore Runtime entrypoint for ARM64
7. THE CDK stack SHALL output the AgentCore Runtime ARN, Runtime ID, and ECR repository URI as CloudFormation outputs
8. THE CDK stack SHALL create a `bedrockagentcore.CfnRuntime` resource with the container URI from ECR, network configuration, and environment variables to provision the AgentCore Runtime directly
9. THE CDK stack SHALL create an AgentCore execution IAM role assumed by `bedrock-agentcore.amazonaws.com` with permissions for ECR pull, CloudWatch logs, X-Ray, Bedrock model invocation, SSM parameter read, DynamoDB read, OpenSearch access, and Personalize access
10. THE CDK stack SHALL use a Lambda custom resource to trigger CodeBuild and wait for build completion before creating the CfnRuntime resource

### Requirement 11: VPC Configuration as Deployment Parameter

**User Story:** As a developer, I want to optionally specify VPC configuration for deployment, so that the AgentCore Runtime can be deployed within a specific VPC for network isolation and access to VPC-only resources like OpenSearch Serverless.

#### Acceptance Criteria

1. THE CDK stack SHALL accept an optional VPC network mode (`PUBLIC` or `PRIVATE`) as a CDK context parameter
2. WHEN network mode is `PRIVATE`, THE CDK stack SHALL accept subnet IDs and security group IDs as CDK context parameters
3. THE CfnRuntime resource SHALL be configured with the specified network mode, subnets, and security groups
4. THE Deploy_Script SHALL pass VPC-related parameters to CDK as context parameters when provided

### Requirement 12: Service Parameters in CDK Stack

**User Story:** As a developer, I want deployment parameters (AOSS endpoint, DynamoDB table names, Personalize ARN) provisioned as AWS Systems Manager Parameter Store entries via CDK, so that configuration is centrally managed as infrastructure-as-code.

#### Acceptance Criteria

1. THE CDK stack SHALL create a Parameter_Store parameter for the AOSS collection endpoint under a namespaced path
2. THE CDK stack SHALL create a Parameter_Store parameter for the DynamoDB item table name under a namespaced path
3. THE CDK stack SHALL create a Parameter_Store parameter for the DynamoDB user table name under a namespaced path
4. THE CDK stack SHALL create a Parameter_Store parameter for the Amazon Personalize recommender ARN under a namespaced path
5. THE CDK stack SHALL use a consistent parameter path prefix (e.g., `/agentcore/sales-agent/`) for all stored parameters
6. WHEN the CDK stack is redeployed with updated parameter values, THE CDK stack SHALL update the existing Parameter_Store values

### Requirement 13: Runtime Reads from Parameter Store

**User Story:** As a developer, I want the AgentCore Runtime agent to read configuration values from Parameter Store at startup, so that configuration changes do not require code redeployment.

#### Acceptance Criteria

1. WHEN the Sales_Agent starts, THE Sales_Agent SHALL attempt to read the AOSS collection endpoint from Parameter_Store using the namespaced path
2. WHEN the Sales_Agent starts, THE Sales_Agent SHALL attempt to read the DynamoDB item table name from Parameter_Store using the namespaced path
3. WHEN the Sales_Agent starts, THE Sales_Agent SHALL attempt to read the DynamoDB user table name from Parameter_Store using the namespaced path
4. WHEN the Sales_Agent starts, THE Sales_Agent SHALL attempt to read the Amazon Personalize recommender ARN from Parameter_Store using the namespaced path
5. IF a parameter is not found in Parameter_Store, THEN THE Sales_Agent SHALL fall back to reading the corresponding environment variable
6. THE Sales_Agent SHALL read the parameter path prefix from the `PARAMETER_STORE_PREFIX` environment variable, defaulting to `/agentcore/sales-agent/`

### Requirement 14: Deploy Script

**User Story:** As a developer, I want a single deploy script that orchestrates CDK deployment to provision the full AgentCore Runtime stack, so that I can deploy everything with one command.

#### Acceptance Criteria

1. THE Deploy_Script SHALL be a shell script located at `agent-core/deploy.sh`
2. THE Deploy_Script SHALL run `cdk deploy` to provision the full CDK stack (ECR repository, CodeBuild project, CodeBuild trigger, CfnRuntime, SSM parameters)
3. THE Deploy_Script SHALL accept command-line arguments for AOSS endpoint, DynamoDB table names, Personalize ARN, network mode, subnets, security groups, and AWS region, passing them as CDK context parameters
4. THE Deploy_Script SHALL extract the Runtime ARN and ECR URI from CDK outputs and display them
5. THE Deploy_Script SHALL print a deployment summary with a test command upon successful completion
6. IF any step in the deployment fails, THEN THE Deploy_Script SHALL exit with a non-zero status code and print a descriptive error message indicating which step failed

### Requirement 15: Chat CLI

**User Story:** As a developer, I want a command-line interface tool to interactively chat with the deployed AgentCore Runtime agent, so that I can test and debug the agent conversationally.

#### Acceptance Criteria

1. THE Chat_CLI SHALL be a Python script located at `agent-core/chat_cli.py`
2. THE Chat_CLI SHALL accept the AgentCore Runtime agent endpoint as a command-line argument or read it from the `AGENTCORE_ENDPOINT` environment variable
3. WHEN the Chat_CLI starts, THE Chat_CLI SHALL display a welcome message and prompt the user for input
4. WHEN the user enters a message, THE Chat_CLI SHALL send the message as a `prompt` field in the payload to the AgentCore_Runtime agent endpoint and display the response
5. THE Chat_CLI SHALL maintain a conversational session, allowing the user to send multiple messages without restarting
6. WHEN the user types `exit` or `quit`, THE Chat_CLI SHALL end the session gracefully with a farewell message
7. IF the AgentCore_Runtime agent endpoint is unreachable, THEN THE Chat_CLI SHALL display a descriptive error message indicating the connection failure and allow the user to retry
8. THE Chat_CLI SHALL accept an optional `--user-id` argument to include a user identifier in the payload for personalized interactions
