# Implementation Plan: Sales Agent CLI

## Overview

Replace the existing `agent-core/chat_cli.py` with a full-featured Click-based CLI package at `agent-core/cli/`. Implementation proceeds bottom-up: package structure and core class first, then streaming module, then individual commands, and finally wiring and integration.

## Tasks

- [x] 1. Set up CLI package structure and dependencies
  - [x] 1.1 Create `agent-core/cli/__init__.py` with `__version__ = "0.1.0"`
  - [x] 1.2 Create `agent-core/cli/sales_agent_cli.py` with the Click command group entry point, `--stack-name` option (with `AGENTCORE_STACK_NAME` env var fallback), and `-v`/`-vv` verbosity flags
    - Implement the `cli` Click group with `@click.group()`, `--stack-name` option, and `verbose` count option
    - Store `stack_name` and `verbosity` in `ctx.obj`
    - Exit with error if no stack name is provided when required
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 1.8, 1.9_
  - [x] 1.3 Implement the `SalesAgentCLI` class with `validate_credentials()`, `validate_stack()`, `get_runtime_arn()`, `get_ssm_prefix()`, `get_log_group()`, and `create_client()` methods
    - `validate_credentials()`: call STS `GetCallerIdentity`, raise `ClickException` on failure with STS error details
    - `validate_stack()`: call `describe_stacks`, cache outputs, raise `ClickException` if stack not found
    - `get_runtime_arn()`: return `RuntimeArn` from stack outputs, fallback to listing runtimes via SDK
    - `get_ssm_prefix()`: derive from stack outputs or default to `/{stack_name}/`
    - `get_log_group()`: derive from RuntimeId as `/aws/bedrock-agentcore/runtimes/{id}-DEFAULT`
    - _Requirements: 1.5, 1.6, 2.1, 2.2, 2.3_
  - [x] 1.4 Add `click` and `websockets` to `agent-core/requirements.txt`
    - _Requirements: 10.2_

- [x] 2. Implement the streaming response handler module
  - [x] 2.1 Create `agent-core/cli/streaming.py` with `PerformanceMetrics` dataclass and `StreamingResponseHandler` class
    - Implement `PerformanceMetrics` with `time_to_first_token` and `total_duration` fields
    - Implement `handle_stream(websocket)` async method with thinking spinner, `<thinking>` tag parsing state machine (WAITING → THINKING → RESPONDING), chunk concatenation, and TTFB/total duration recording
    - Implement `_start_spinner()`, `_update_spinner(thinking_text)`, `_stop_spinner()` using `click.echo` with `\r` carriage return
    - On stream error, return partial response text and surface error message
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
  - [ ]* 2.2 Write property test for thinking tag extraction
    - **Property 11: Thinking tag content extraction**
    - **Validates: Requirements 6.3**
  - [ ]* 2.3 Write property test for stream completion
    - **Property 12: Stream completion returns concatenated response with metrics**
    - **Validates: Requirements 4.6, 6.6**
  - [ ]* 2.4 Write property test for partial response on error
    - **Property 13: Partial response on stream error**
    - **Validates: Requirements 6.7**
  - [ ]* 2.5 Write property test for TTFB recording
    - **Property 9: Performance metrics TTFB recording**
    - **Validates: Requirements 5.9, 6.5**

- [x] 3. Checkpoint - Ensure core modules work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement the `version` command
  - [x] 4.1 Add `version` command to `sales_agent_cli.py` that prints `cli.__version__`
    - _Requirements: 9.1, 9.2_

- [x] 5. Implement the `param` command group
  - [x] 5.1 Add `param` command group with `set`, `get`, and `list` subcommands
    - `param set --key <key> --value <value>`: call `put_parameter` at `{prefix}/{key}`
    - `param get --key <key>`: call `get_parameter` at `{prefix}/{key}`, display value, show error if not found
    - `param list`: call `get_parameters_by_path` under `{prefix}/`, display all names and values, show message if none found
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_
  - [ ]* 5.2 Write property test for SSM prefix derivation
    - **Property 4: SSM prefix derivation**
    - **Validates: Requirements 3.2**
  - [ ]* 5.3 Write property test for parameter set/get round trip
    - **Property 5: Parameter set/get round trip**
    - **Validates: Requirements 3.3, 3.4**
  - [ ]* 5.4 Write property test for parameter list completeness
    - **Property 6: Parameter list completeness**
    - **Validates: Requirements 3.6**

- [x] 6. Implement the `invoke` command
  - [x] 6.1 Add `invoke` command with `--message`, `--session-id`, and `--actor-id` options
    - Resolve Runtime ARN via `SalesAgentCLI.get_runtime_arn()`
    - Create `AgentCoreRuntimeClient`, generate presigned URL, open WebSocket
    - Send message payload (include session_id if provided)
    - Delegate streaming to `StreamingResponseHandler.handle_stream()`
    - Display response and performance metrics at verbose level
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  - [ ]* 6.2 Write property test for session ID in payload
    - **Property 7: Session ID in invocation payload**
    - **Validates: Requirements 4.7**

- [x] 7. Implement the `chat` command
  - [x] 7.1 Add `chat` command with interactive REPL loop
    - Generate UUID4 session ID at start
    - REPL loop: read input, dispatch slash commands (`/exit`, `/quit`, `/q`, `/clear`, `/session`, `/help`), send messages via same invoke path as `invoke` command
    - `/clear` generates new session ID, `/session` displays current ID, `/help` lists commands
    - Track `PerformanceMetrics` per invocation
    - Log all interactions to `~/.sales-agent-cli/logs/{session_id}.jsonl` with timestamps
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_
  - [ ]* 7.2 Write property test for chat session ID uniqueness
    - **Property 8: Chat session ID uniqueness**
    - **Validates: Requirements 5.2**
  - [ ]* 7.3 Write property test for chat interaction logging round trip
    - **Property 10: Chat interaction logging round trip**
    - **Validates: Requirements 5.10**

- [x] 8. Checkpoint - Ensure invoke and chat work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement the `logs` command
  - [x] 9.1 Add `logs` command with `--tail`, `--start`, and `--end` options
    - Derive log group via `SalesAgentCLI.get_log_group()`
    - Implement time expression parser supporting ISO 8601 and relative expressions (`1h ago`, `30m ago`)
    - Call `filter_log_events` with time filters
    - Color-code output by severity (ERROR=red, WARN=yellow, INFO=default, DEBUG=dim)
    - Parse and pretty-print structured JSON in log messages
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [ ]* 9.2 Write property test for time expression parsing
    - **Property 15: Time expression parsing**
    - **Validates: Requirements 7.3, 7.4**
  - [ ]* 9.3 Write property test for log severity color mapping
    - **Property 16: Log severity color mapping**
    - **Validates: Requirements 7.5**
  - [ ]* 9.4 Write property test for JSON log formatting
    - **Property 17: JSON log formatting**
    - **Validates: Requirements 7.6**
  - [ ]* 9.5 Write property test for log tail count
    - **Property 14: Log tail returns requested count**
    - **Validates: Requirements 7.2**

- [x] 10. Implement the `status` command
  - [x] 10.1 Add `status` command displaying stack info, outputs, and ECS health
    - Display CloudFormation stack name, status, and all stack outputs
    - Query ECS `describe_services` for desired/running/pending task counts
    - Show recent CloudFormation events if stack is in a transitional state (`*_IN_PROGRESS`)
    - Display message if stack not found
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [ ]* 10.2 Write property test for stack output display completeness
    - **Property 18: Status displays all stack outputs**
    - **Validates: Requirements 8.2**
  - [ ]* 10.3 Write property test for transitional state detection
    - **Property 19: Transitional state detection**
    - **Validates: Requirements 8.4**

- [x] 11. Wire everything together and finalize
  - [x] 11.1 Add `__main__.py` support so CLI is runnable via `python -m cli.sales_agent_cli`
    - _Requirements: 10.3_
  - [x] 11.2 Ensure shared stack validation decorator/helper is used by all commands that require a stack (`invoke`, `chat`, `param`, `logs`, `status`)
    - _Requirements: 1.5, 2.1_
  - [ ]* 11.3 Write property tests for stack name env var fallback and verbosity flags
    - **Property 1: Stack name environment variable fallback**
    - **Property 2: Verbosity flag count**
    - **Validates: Requirements 1.3, 1.7**
  - [ ]* 11.4 Write property test for stack output extraction
    - **Property 3: Stack output extraction**
    - **Validates: Requirements 2.3**

- [x] 12. Set up test infrastructure
  - [x] 12.1 Create test directory structure at `agent-core/tests/cli/` with `__init__.py`, `test_sales_agent_cli.py`, `test_streaming.py`, and `test_time_parser.py`
    - Add `hypothesis`, `pytest-mock`, and `moto` to dev dependencies if not present
    - _Requirements: 10.1_

- [-] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The existing `agent-core/chat_cli.py` is replaced by the new CLI package (Requirement 10.4)
