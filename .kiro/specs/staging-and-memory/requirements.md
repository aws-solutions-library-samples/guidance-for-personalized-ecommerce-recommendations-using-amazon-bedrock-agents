# Requirements Document

## Introduction

This feature adds two capabilities to the AgentCore Sales Agent project:

1. **Staging Deployment** — A separate staging environment alongside the existing production deployment, with isolated resources and environment-specific configuration. The existing CLI already supports targeting different stacks via `--stack-name`, so no CLI changes are required.

2. **Bedrock AgentCore Memory** — Integration with Bedrock AgentCore's built-in memory service for short-term conversation memory, allowing the agent to remember previous messages within a session without the caller resending history.

## Glossary

- **CDK_Stack**: The AWS CDK infrastructure-as-code stack that provisions all AgentCore resources (ECR, CodeBuild, CfnRuntime, SSM parameters, IAM roles).
- **Environment**: A named deployment target, either `staging` or `production`, each with isolated AWS resources.
- **Parameter_Store_Prefix**: The SSM Parameter Store path prefix used to namespace configuration values per environment (e.g., `/agentcore/sales-agent/staging/`).
- **CfnRuntime**: The Bedrock AgentCore CloudFormation runtime resource that hosts the containerized agent.
- **Agent**: The Strands Agents SDK agent instance defined in `agent.py` that processes user prompts.
- **Memory_Service**: Bedrock AgentCore's built-in memory API used to store and retrieve short-term conversation context.
- **Session**: A conversation identified by a unique session ID, within which the Agent retains short-term memory of previous exchanges.
- **Deploy_Script**: The `deploy.sh` bash script that wraps CDK deployment with CLI arguments.

## Requirements

### Requirement 1: Environment-Parameterized CDK Stack

**User Story:** As a developer, I want the CDK stack to accept an environment parameter, so that I can deploy separate staging and production stacks with isolated resources.

#### Acceptance Criteria

1. WHEN an environment name is provided via CDK context, THE CDK_Stack SHALL use the environment name to generate unique resource names and identifiers for all provisioned resources.
2. WHEN no environment name is provided via CDK context, THE CDK_Stack SHALL default to the environment name `production`.
3. THE CDK_Stack SHALL use a distinct Parameter_Store_Prefix for each Environment (e.g., `/agentcore/sales-agent/staging/` vs `/agentcore/sales-agent/production/`).
4. THE CDK_Stack SHALL assign a unique CfnRuntime name per Environment to prevent naming collisions.
5. THE CDK_Stack SHALL create a separate ECR repository per Environment.

### Requirement 2: Environment-Aware Deploy Script

**User Story:** As a developer, I want the deploy script to support an environment flag, so that I can deploy to staging or production from the command line.

#### Acceptance Criteria

1. WHEN the `--env` flag is provided to the Deploy_Script, THE Deploy_Script SHALL pass the environment name as CDK context to the CDK_Stack.
2. WHEN the `--env` flag is not provided, THE Deploy_Script SHALL default to the `production` environment.
3. THE Deploy_Script SHALL set the CDK stack name to include the Environment name (e.g., `AgentCoreStack-staging`).
4. THE Deploy_Script SHALL write deployment outputs to an environment-specific file (e.g., `cdk-outputs-staging.json`).

### Requirement 3: Environment-Specific Configuration Resolution

**User Story:** As a developer, I want the agent configuration to resolve from the correct environment-specific parameter path, so that staging and production use independent settings.

#### Acceptance Criteria

1. THE Config SHALL read the Parameter_Store_Prefix from the `PARAMETER_STORE_PREFIX` environment variable set by the CfnRuntime for the active Environment.
2. WHEN the `PARAMETER_STORE_PREFIX` environment variable is set, THE Config SHALL use the specified prefix to load all configuration parameters.
3. THE Config SHALL resolve each configuration field from Parameter Store, then environment variables, then defaults, in that order.

### Requirement 4: Short-Term Memory Integration

**User Story:** As a user, I want the agent to remember previous messages in my conversation, so that I do not need to repeat context in multi-turn interactions.

#### Acceptance Criteria

1. WHEN a prompt is received with a session ID, THE Agent SHALL retrieve the conversation history for the Session from the Memory_Service before generating a response.
2. WHEN the Agent generates a response, THE Agent SHALL store both the user prompt and the agent response in the Memory_Service under the Session.
3. WHEN a prompt is received without a session ID, THE Agent SHALL create a new Session and store the exchange in the Memory_Service.
4. THE Agent SHALL include the retrieved conversation history as context when invoking the language model.
5. IF the Memory_Service is unreachable, THEN THE Agent SHALL log a warning and process the prompt without conversation history.

### Requirement 5: Memory-Aware WebSocket Handler

**User Story:** As a platform consumer, I want the WebSocket handler to support session-based memory, so that multi-turn conversations over WebSocket retain context.

#### Acceptance Criteria

1. WHEN a WebSocket message includes a `session_id` field, THE Agent SHALL use the provided session ID for memory retrieval and storage.
2. WHEN a WebSocket message does not include a `session_id` field, THE Agent SHALL generate a new session ID for the exchange.
3. THE Agent SHALL store each WebSocket exchange (prompt and response) in the Memory_Service under the active Session.

### Requirement 6: Memory-Aware HTTP Entrypoint

**User Story:** As a platform consumer, I want the HTTP entrypoint to support session-based memory, so that multi-turn conversations over HTTP retain context.

#### Acceptance Criteria

1. WHEN an HTTP payload includes a `session_id` field, THE Agent SHALL use the provided session ID for memory retrieval and storage.
2. WHEN an HTTP payload does not include a `session_id` field, THE Agent SHALL generate a new session ID for the exchange.
3. THE Agent SHALL store each HTTP exchange (prompt and response) in the Memory_Service under the active Session.

