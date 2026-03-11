# Requirements Document

## Introduction

Replace the existing simple HTTP-based chat CLI (`agent-core/chat_cli.py`) with a full-featured Click-based CLI tool (`agent-core/cli/`) that provides multi-command support for interacting with the deployed AgentCore Sales Agent. The CLI uses the Bedrock AgentCore SDK directly (via WebSocket) instead of HTTP POST, and adds operational commands for parameter management, log retrieval, deployment status, and streaming chat sessions.

## Glossary

- **CLI**: The Click-based command-line interface application located at `agent-core/cli/sales_agent_cli.py`
- **Stack_Name**: The CloudFormation stack name (e.g. `AgentCoreStack`) used to identify the deployed infrastructure and derive resource references such as Runtime ARN, log group, and SSM parameter prefix
- **Parameter_Store**: AWS Systems Manager Parameter Store, used to store configuration values under a prefix derived from the stack
- **Runtime**: The Bedrock AgentCore Runtime resource that hosts the Sales Agent container
- **Runtime_ARN**: The Amazon Resource Name uniquely identifying a deployed AgentCore Runtime
- **CloudFormation_Stack**: The AWS CDK-deployed stack identified by Stack_Name containing the Runtime and supporting resources
- **Session_ID**: A unique identifier for a multi-turn conversation with the agent, maintained across messages within a chat session
- **Streaming_Response_Handler**: A module (`cli/streaming.py`) responsible for processing streamed WebSocket responses from the AgentCore Runtime and rendering them to the terminal
- **Performance_Metrics**: A class that tracks timing data (time-to-first-token, total duration) for agent invocations
- **Log_Group**: The CloudWatch Logs log group associated with the AgentCore Runtime, following the pattern `/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT`
- **Verbosity**: A global output detail level controlled by `-v` (verbose) and `-vv` (debug) flags on the top-level CLI group, affecting all subcommands

## Requirements

### Requirement 1: CLI Entry Point, Stack Name, and Verbosity

**User Story:** As a developer, I want a single CLI entry point with a global `--stack-name` option and verbosity flags, so that all commands operate against the correct deployment stack and I can control output detail level.

#### Acceptance Criteria

1. THE CLI SHALL provide a Click-based command group as the top-level entry point
2. THE CLI SHALL accept a `--stack-name` option on the top-level group, applicable to all subcommands
3. WHEN the `--stack-name` option is not provided, THE CLI SHALL read the stack name from the `AGENTCORE_STACK_NAME` environment variable
4. IF neither `--stack-name` nor `AGENTCORE_STACK_NAME` is provided, THEN THE CLI SHALL exit with an error message indicating that a stack name is required
5. THE CLI SHALL validate AWS credentials by checking STS `GetCallerIdentity` before executing any command
6. IF AWS credentials are invalid or expired, THEN THE CLI SHALL exit with a descriptive error message including the STS error details
7. THE CLI SHALL accept `-v` and `-vv` flags on the top-level group to set global verbosity level (0=normal, 1=verbose, 2=debug), applicable to all subcommands
8. WHEN verbosity is 1 (`-v`), THE CLI SHALL display additional operational details such as resolved ARNs, API call parameters, and performance metrics
9. WHEN verbosity is 2 (`-vv`), THE CLI SHALL display all debug-level output including raw API responses and streaming event details

### Requirement 2: Stack Validation

**User Story:** As a developer, I want the CLI to validate that my chosen stack exists, so that I do not accidentally run commands against a non-existent deployment.

#### Acceptance Criteria

1. WHEN a stack name is provided, THE CLI SHALL verify the CloudFormation stack exists by calling `describe_stacks`
2. IF the CloudFormation stack does not exist, THEN THE CLI SHALL exit with an error message stating the stack was not found
3. WHEN the stack is validated, THE CLI SHALL extract and cache the stack outputs (RuntimeArn, EcrRepositoryUri, etc.) for use by subcommands

### Requirement 3: Parameter Management Commands

**User Story:** As a developer, I want to manage Parameter Store values for my deployment from the CLI, so that I can configure the agent without using the AWS Console.

#### Acceptance Criteria

1. THE CLI SHALL provide a `param` command group containing `set`, `get`, and `list` subcommands
2. THE CLI SHALL derive the SSM parameter prefix from the CloudFormation stack outputs or use a default prefix based on the stack name
3. WHEN `param set --key <key> --value <value>` is invoked, THE CLI SHALL create or update the parameter at `{prefix}/{key}` with the provided value
4. WHEN `param get --key <key>` is invoked, THE CLI SHALL retrieve and display the value of the parameter at `{prefix}/{key}`
5. IF the requested parameter does not exist, THEN THE CLI SHALL display an error message stating the parameter was not found
6. WHEN `param list` is invoked, THE CLI SHALL retrieve and display all parameter names and values under the `{prefix}/` path
7. IF no parameters exist under the prefix, THEN THE CLI SHALL display a message indicating no parameters were found

### Requirement 4: Single Message Invocation

**User Story:** As a developer, I want to send a single message to the agent and receive a response, so that I can quickly test agent behavior without entering an interactive session.

#### Acceptance Criteria

1. THE CLI SHALL provide an `invoke` command that accepts `--message`, `--session-id`, and `--actor-id` options
2. WHEN `invoke` is executed, THE CLI SHALL resolve the Runtime ARN by querying CloudFormation stack outputs for the `RuntimeArn` output
3. IF the CloudFormation stack does not exist or has no `RuntimeArn` output, THEN THE CLI SHALL attempt to resolve the Runtime ARN by listing AgentCore runtimes via the Bedrock AgentCore SDK
4. IF no Runtime ARN can be resolved, THEN THE CLI SHALL exit with an error message
5. WHEN the Runtime ARN is resolved, THE CLI SHALL invoke the runtime using the Bedrock AgentCore SDK `AgentCoreRuntimeClient` with WebSocket streaming
6. THE CLI SHALL stream the agent response to the terminal in real-time as chunks arrive
7. WHEN the `--session-id` option is provided, THE CLI SHALL include the session ID in the invocation payload

### Requirement 5: Interactive Chat Session

**User Story:** As a developer, I want an interactive multi-turn chat session with the agent, so that I can have extended conversations and test conversational flows.

#### Acceptance Criteria

1. THE CLI SHALL provide a `chat` command that starts an interactive REPL session
2. THE CLI SHALL generate a unique session ID at the start of each chat session and maintain the session ID across all messages in the session
3. WHEN the user types a message and presses Enter, THE CLI SHALL send the message to the agent runtime via WebSocket streaming and display the streamed response
4. WHEN the user types `/exit`, `/quit`, or `/q`, THE CLI SHALL end the chat session gracefully
5. WHEN the user types `/clear`, THE CLI SHALL generate a new session ID and display a confirmation message
6. WHEN the user types `/session`, THE CLI SHALL display the current session ID
7. WHEN the user types `/help`, THE CLI SHALL display a list of available slash commands with descriptions
8. THE CLI SHALL inherit the global verbosity level from the top-level group for controlling debug output in the chat session
9. THE CLI SHALL track Performance_Metrics (time-to-first-token, total response duration) for each agent invocation
10. THE CLI SHALL automatically log all chat interactions to files under `~/.sales-agent-cli/logs/` with timestamps

### Requirement 6: Streaming Response Handler

**User Story:** As a developer, I want agent responses to stream to my terminal in real-time, so that I do not have to wait for the full response before seeing output.

#### Acceptance Criteria

1. THE Streaming_Response_Handler SHALL be implemented as a separate module at `agent-core/cli/streaming.py`
2. WHEN waiting for the first response chunk, THE Streaming_Response_Handler SHALL display an animated "thinking" spinner to indicate the agent is processing
3. WHEN a streamed chunk contains a `<thinking>` tag, THE Streaming_Response_Handler SHALL display the text within the tag alongside the thinking spinner as a status update
4. WHEN the first non-thinking response chunk is received, THE Streaming_Response_Handler SHALL stop the thinking spinner and begin writing chunk text to the terminal on a new line without buffering
5. THE Streaming_Response_Handler SHALL record the timestamp of the first received chunk as the time-to-first-token metric
6. WHEN the stream completes, THE Streaming_Response_Handler SHALL record the total duration and return the complete response text along with Performance_Metrics
7. IF a stream error occurs, THEN THE Streaming_Response_Handler SHALL display the error message and return a partial response if any chunks were received

### Requirement 7: CloudWatch Log Retrieval

**User Story:** As a developer, I want to view CloudWatch logs for my agent runtime from the CLI, so that I can debug issues without switching to the AWS Console.

#### Acceptance Criteria

1. THE CLI SHALL provide a `logs` command for retrieving CloudWatch logs from the agent runtime log group
2. WHEN `logs --tail <N>` is invoked, THE CLI SHALL display the most recent N log lines from the runtime log group
3. WHEN `logs --start <time>` is invoked, THE CLI SHALL filter logs starting from the specified time, supporting both ISO 8601 format and relative expressions (e.g. `1h ago`, `30m ago`)
4. WHEN `logs --end <time>` is invoked, THE CLI SHALL filter logs up to the specified time, supporting the same formats as `--start`
5. THE CLI SHALL color-code log output by severity level (e.g. ERROR in red, WARN in yellow, INFO in default)
6. WHEN a log message contains structured JSON, THE CLI SHALL parse and format the JSON for readability

### Requirement 8: Deployment Status

**User Story:** As a developer, I want to check the deployment status of my agent from the CLI, so that I can verify the infrastructure is healthy.

#### Acceptance Criteria

1. THE CLI SHALL provide a `status` command that displays deployment information for the current stack
2. WHEN `status` is invoked, THE CLI SHALL display the CloudFormation stack name, status, and all stack outputs
3. WHEN `status` is invoked, THE CLI SHALL display ECS service health information including desired, running, and pending task counts
4. WHILE the CloudFormation stack is in a transitional state (e.g. `CREATE_IN_PROGRESS`, `UPDATE_IN_PROGRESS`), THE CLI SHALL display the most recent CloudFormation events
5. IF the CloudFormation stack does not exist, THEN THE CLI SHALL display a message indicating no deployment was found for the stack name

### Requirement 9: Version Command

**User Story:** As a developer, I want to check the CLI version, so that I can verify I am running the expected version.

#### Acceptance Criteria

1. THE CLI SHALL provide a `version` command that displays the CLI version string
2. THE CLI SHALL read the version from a `__version__` variable defined in the `cli/__init__.py` module

### Requirement 10: CLI Package Structure

**User Story:** As a developer, I want the CLI organized as a proper Python package, so that it is maintainable and can be installed as a tool.

#### Acceptance Criteria

1. THE CLI SHALL be structured as a Python package at `agent-core/cli/` with `__init__.py`, `sales_agent_cli.py`, and `streaming.py` modules
2. THE CLI SHALL declare `click` as a required dependency in the project requirements
3. THE CLI SHALL be executable via `python -m cli.sales_agent_cli` from the `agent-core/` directory
4. THE CLI SHALL replace the existing `agent-core/chat_cli.py` as the primary command-line interface for the project
