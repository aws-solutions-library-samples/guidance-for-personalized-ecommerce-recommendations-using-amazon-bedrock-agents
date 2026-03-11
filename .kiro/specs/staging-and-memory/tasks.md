# Implementation Plan: Staging and Memory

## Overview

Bottom-up implementation: first parameterize CDK infrastructure for multi-environment support, then update the deploy script, then add the MemoryClient module and integrate it into agent handlers. Tests are co-located with their implementation tasks.

## Tasks

- [x] 1. CDK stack environment parameterization
  - [x] 1.1 Add `env-name` context parameter to `agentcore_stack.py` with `production` default
    - Read `env-name` from `self.node.try_get_context("env-name")`, default to `"production"`
    - Use env name in CfnRuntime `agent_runtime_name`: `agentcore_sales_agent_{env}`
    - Use env name in SSM `param_prefix`: `/agentcore/sales-agent/{env}`
    - Use env name in `PARAMETER_STORE_PREFIX` env var: `/agentcore/sales-agent/{env}/`
    - Use env name in ECR repository logical ID (e.g., `AgentCoreEcrRepo-{env}`)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Add `memory-id` context parameter and `MEMORY_ID` env var to CfnRuntime
    - Read `memory-id` from CDK context, default to empty string
    - Add `MEMORY_ID` to the CfnRuntime `environment_variables` dict
    - _Requirements: 4.1_

  - [x] 1.3 Add memory service IAM permissions to `agentcore_role.py`
    - Add `bedrock-agentcore:memory:*` actions to the execution role policy
    - Resource: `*`
    - _Requirements: 4.1, 4.2_

  - [ ]* 1.4 Write property test for environment name in resource identifiers
    - **Property 1: Environment name embedded in all resource identifiers**
    - Use `hypothesis` to generate random alphanumeric env names
    - Synthesize CDK template or call naming logic, verify env name appears in CfnRuntime name, SSM prefix, and ECR logical ID
    - Verify two distinct env names produce distinct identifiers
    - **Validates: Requirements 1.1, 1.3, 1.4, 1.5**

  - [ ]* 1.5 Write unit tests for CDK stack defaults
    - Verify omitting `env-name` context produces `production` in resource names
    - Verify `MEMORY_ID` env var is set on CfnRuntime
    - Verify SSM parameter prefix includes env name
    - **Validates: Requirements 1.2**

- [x] 2. CDK app entry point update
  - [x] 2.1 Update `cdk/app.py` to read `env-name` and create env-aware stack ID
    - Read `env-name` from `app.node.try_get_context("env-name")`, default to `"production"`
    - Pass env name to `AgentCoreStack` constructor
    - Set stack ID to `AgentCoreStack-{env}`
    - _Requirements: 2.3_

- [x] 3. Deploy script updates
  - [x] 3.1 Add `--env` and `--memory-id` flags to `deploy.sh`
    - Add `--env` flag with default `production`
    - Add `--memory-id` flag (optional)
    - Pass `--context env-name={env}` to CDK
    - Pass `--context memory-id={id}` to CDK when provided
    - Set stack name to `AgentCoreStack-{env}` in the `cdk deploy` command
    - Write outputs to `cdk-outputs-{env}.json`
    - Extract outputs using `AgentCoreStack-{env}` key from the JSON
    - Update usage comment at top of script
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.2 Write unit tests for deploy script behavior
    - Test `--env` defaults to `production`
    - Test `--env staging` passes `--context env-name=staging`
    - Test stack name is `AgentCoreStack-{env}`
    - Test output file is `cdk-outputs-{env}.json`
    - Test `--memory-id` passes `--context memory-id={id}`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 4. Checkpoint — Verify staging infrastructure
  - Ensure all tests pass, ask the user if questions arise.
  - Verify CDK synth produces correct resource names for both `staging` and `production` environments.

- [x] 5. MemoryClient module
  - [x] 5.1 Create `agentcore-runtime/memory.py` with `MemoryClient` class
    - `__init__(self, memory_id: str)` — initialize with memory resource ID
    - `get_history(self, session_id: str, actor_id: str = "user", last_k: int = 10) -> list[dict]` — retrieve last K turns, return empty list on error
    - `store_turn(self, session_id: str, actor_id: str, role: str, content: str) -> None` — store a single turn, log warning on error
    - All methods catch exceptions, log warnings, and continue (graceful degradation)
    - Use `bedrock-agentcore` SDK's memory/session APIs
    - _Requirements: 4.1, 4.2, 4.5_

  - [ ]* 5.2 Write property test for graceful degradation on memory failure
    - **Property 8: Graceful degradation on memory service failure**
    - Use `hypothesis` to generate random prompts and session IDs
    - Mock memory service to raise exceptions
    - Verify `get_history` returns empty list (no exception raised)
    - Verify `store_turn` does not raise (logs warning)
    - **Validates: Requirements 4.5**

  - [ ]* 5.3 Write unit tests for MemoryClient
    - Test `MemoryClient` initialization
    - Test `get_history` returns empty list when no history exists
    - Test `store_turn` stores correctly with mocked SDK
    - **Validates: Requirements 4.1, 4.2**

- [x] 6. Agent handler memory integration
  - [x] 6.1 Update HTTP entrypoint (`invoke`) in `agent.py` with memory support
    - Initialize `MemoryClient` at module level if `MEMORY_ID` env var is set, else `None`
    - Extract `session_id` from payload, generate UUID v4 if absent
    - Call `memory_client.get_history(session_id)` before agent invocation (skip if client is `None`)
    - Prepend conversation history to prompt as context
    - After response, call `memory_client.store_turn()` for user message (role `"user"`) and assistant response (role `"assistant"`)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2, 6.3_

  - [x] 6.2 Update WebSocket handler (`ws_handler`) in `agent.py` with memory support
    - Extract `session_id` from payload, generate UUID v4 if absent
    - Call `memory_client.get_history(session_id)` before agent invocation (skip if client is `None`)
    - Prepend conversation history to prompt as context
    - After response, call `memory_client.store_turn()` for user message and assistant response
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3_

  - [ ]* 6.3 Write property test: provided session ID used for memory operations
    - **Property 4: Provided session ID used for memory operations**
    - Use `hypothesis` to generate random session_id strings and prompts
    - Mock memory client, invoke handler, verify session_id passed to `get_history` and `store_turn`
    - **Validates: Requirements 4.1, 5.1, 6.1**

  - [ ]* 6.4 Write property test: missing session ID generates new UUID
    - **Property 5: Missing session ID generates a new valid UUID**
    - Use `hypothesis` to generate random prompts without session_id
    - Invoke handler, verify generated ID is valid UUID v4
    - **Validates: Requirements 4.3, 5.2, 6.2**

  - [ ]* 6.5 Write property test: conversation history included in prompt
    - **Property 6: Conversation history included in prompt context**
    - Use `hypothesis` to generate random history turn lists
    - Mock memory client to return them, verify agent receives prompt containing history content
    - **Validates: Requirements 4.4**

  - [ ]* 6.6 Write property test: both turns stored after exchange
    - **Property 7: Both user and assistant turns stored after exchange**
    - Use `hypothesis` to generate random prompt/response pairs
    - Mock agent and memory, verify exactly two `store_turn` calls with correct roles
    - **Validates: Requirements 4.2, 5.3, 6.3**

- [x] 7. Checkpoint — Verify memory integration
  - Ensure all tests pass, ask the user if questions arise.
  - Verify agent works with and without `MEMORY_ID` set.

- [x] 8. Update dependencies
  - [x] 8.1 Add `hypothesis` to test dependencies if not present
    - Add `hypothesis` to `requirements.txt` or test dependencies in `pyproject.toml`
    - _Requirements: testing infrastructure_

- [x] 9. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Verify no regressions in existing functionality.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- `config.py` requires no changes — it already reads `PARAMETER_STORE_PREFIX` from env var
- CLI requires no changes — it already supports `--stack-name`
