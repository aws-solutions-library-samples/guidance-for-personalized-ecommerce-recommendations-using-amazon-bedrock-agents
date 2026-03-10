# Implementation Plan: AgentCore Sales Agent

## Overview

Re-implement the existing Bedrock Agent-based sales assistant (`lambda/handler.py`) as a Bedrock AgentCore Runtime application using Strands Agents SDK. The implementation lives in `agent-core/`, uses `uv` for Python package management, and deploys via CDK with ECR, CodeBuild, Lambda custom resource build trigger, and `CfnRuntime`. All tasks use Python.

## Tasks

- [x] 1. Scaffold project structure and dependencies
  - [x] 1.1 Create `agent-core/pyproject.toml` with project metadata and all dependencies
    - Runtime deps: `bedrock-agentcore`, `strands-agents`, `strands-agents-tools`, `opensearch-py`, `boto3`, `requests-aws4auth`
    - CDK deps: `aws-cdk-lib>=2.220.0`, `constructs`
    - Dev deps: `hypothesis>=6.0`, `pytest>=8.0`, `pytest-mock>=3.0`, `moto>=5.0`, `pytest-asyncio>=0.23`
    - _Requirements: 1.2, 1.3_
  - [x] 1.2 Create `agent-core/.env.example` documenting all environment variables
    - Include: `AOSS_COLLECTION_ID`, `AOSS_REGION`, `RECOMMENDER_ARN`, `ITEM_TABLE_NAME`, `USER_TABLE_NAME`, `MODEL_ID`, `PARAMETER_STORE_PREFIX`, `AGENTCORE_ENDPOINT`
    - _Requirements: 7.7_
  - [x] 1.3 Create package init files for `agent-core/tools/__init__.py`, `agent-core/tests/__init__.py`, `agent-core/cdk/__init__.py`, `agent-core/cdk/infra_utils/__init__.py`
    - `tools/__init__.py` exports: `search_product`, `compare_product`, `get_recommendation`
    - _Requirements: 1.1_

- [x] 2. Implement configuration module
  - [x] 2.1 Create `agent-core/config.py` with `Config` dataclass and `Config.load()` classmethod
    - Read `PARAMETER_STORE_PREFIX` env var (default: `/agentcore/sales-agent/`)
    - Call `ssm.get_parameters_by_path(Path=prefix)` to fetch all params in one API call
    - Map parameter names to config fields (e.g., `{prefix}aoss_collection_id` → `aoss_collection_id`)
    - Fall back to corresponding environment variable for any missing parameter
    - Apply defaults: `item_table_name`=`"item_table"`, `user_table_name`=`"user_table"`, `model_id`=`"anthropic.claude-sonnet-4-20250514"`
    - Log warning and fall back entirely to env vars if Parameter Store is unreachable
    - Raise `ValueError` if required fields (`aoss_collection_id`, `aoss_region`) are missing from both sources
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_
  - [ ]* 2.2 Write property test: Config loads from Parameter Store
    - **Property 1: Config loads from Parameter Store**
    - In `agent-core/tests/test_config.py`: use Hypothesis to generate arbitrary config values, mock `ssm.get_parameters_by_path()` to return them, assert `Config.load()` fields match
    - `@settings(max_examples=100)`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 13.1, 13.2, 13.3, 13.4**
  - [ ]* 2.3 Write property test: Config falls back to environment variables with defaults
    - **Property 2: Config falls back to environment variables with defaults**
    - In `agent-core/tests/test_config.py`: use Hypothesis to generate config values, mock Parameter Store as empty/unreachable, set env vars via `monkeypatch`, assert `Config.load()` returns env var values or defaults
    - `@settings(max_examples=100)`
    - **Validates: Requirements 7.4, 7.5, 7.6, 13.5, 13.6**

- [x] 3. Implement shared helper utilities
  - [x] 3.1 Create `agent-core/tools/helpers.py` with shared functions ported from `lambda/handler.py`
    - `get_user_info(user_id, config)`: query DynamoDB `user_table` by `USER_ID`, return dict with `user_id`, `age`, `gender`, `visted`, `add_to_cart`, `purchased`; return descriptive error if user not found
    - `get_item_info(item_id, config)`: query DynamoDB `item_table` by `ITEM_ID`, return dict with `item_id`, `title`, `price`, `style`, `image`; return descriptive error if item not found
    - `get_embedding_for_text(text)`: call Bedrock Runtime `invoke_model` with `amazon.titan-embed-image-v1`, return embedding vector; return descriptive error on failure
    - `call_bedrock_llm(prompt, config)`: invoke Bedrock Claude via `invoke_model` with configurable `model_id`, return text response; return descriptive error on failure
    - `create_opensearch_client(config)`: create `OpenSearch` client with `AWSV4SignerAuth` (service=`aoss`)
    - Each function includes try/except returning descriptive error messages
    - _Requirements: 4.1, 4.4, 4.5, 5.2, 5.3, 6.3, 6.4, 9.1, 9.2, 9.3, 9.5, 9.6_
  - [ ]* 3.2 Write property test: User enrichment retrieves profile and all history items
    - **Property 6: User enrichment retrieves profile and all history items**
    - In `agent-core/tests/test_helpers.py`: use Hypothesis to generate user profiles with varying lists of visited/add-to-cart/purchased item IDs, mock DynamoDB, assert `get_user_info` queries user table once and `get_item_info` is called once per distinct item ID
    - `@settings(max_examples=100)`
    - **Validates: Requirements 5.2, 5.3, 6.3, 6.4**

- [x] 4. Implement product search tool
  - [x] 4.1 Create `agent-core/tools/search_product.py` with `@tool` decorated `search_product(condition: str) -> str`
    - Port logic from `lambda/handler.py` `search_product()`
    - Call `get_embedding_for_text(condition)` → Bedrock Titan Embed Image V1
    - Build AOSS host from `config.aoss_collection_id` + `config.aoss_region` + `.aoss.amazonaws.com`
    - Create `OpenSearch` client with `AWSV4SignerAuth` (service=`aoss`)
    - Execute KNN query on `product-search-multimodal-index` with `k=5`
    - Map hits to product dicts: `item_id`, `score`, `image`, `price`, `style`, `description`
    - Return JSON string of product list (max 5 items)
    - Wrap in try/except returning descriptive error on OpenSearch or embedding failures
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.1, 9.5_
  - [ ]* 4.2 Write property test: Search results have correct format and bounded size
    - **Property 4: Search results have correct format and bounded size**
    - In `agent-core/tests/test_search_product.py`: use Hypothesis to generate lists of 0–10 mock OpenSearch hits, mock OpenSearch client and embedding call, assert output is JSON list of at most 5 items each with exactly fields: `item_id`, `score`, `image`, `price`, `style`, `description`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 4.3**

- [x] 5. Implement product comparison tool
  - [x] 5.1 Create `agent-core/tools/compare_product.py` with `@tool` decorated `compare_product(user_id: str, condition: str, preference: str) -> str`
    - Port logic from `lambda/handler.py` `compare_product()`
    - Call internal search logic (same as `search_product`) to get matching items
    - Call `get_user_info(user_id)` → DynamoDB `user_table` for age, gender, history
    - For each item ID in visited/add_to_cart/purchased, call `get_item_info(item_id)` → DynamoDB `item_table`
    - Construct comparison prompt with user demographics, history, preferences, and available items
    - Call `call_bedrock_llm(prompt)` → Bedrock Claude for comparison summary
    - Return JSON: `{"items": [...], "summarize": "..."}`
    - Wrap in try/except for DynamoDB not-found and Bedrock errors
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 9.2, 9.3, 9.6_
  - [ ]* 5.2 Write property test: Compare tool returns structured output
    - **Property 5: Compare and Recommend tools return structured output**
    - In `agent-core/tests/test_compare_product.py`: use Hypothesis to generate valid inputs, mock all external services, assert returned JSON has `items` (list) and `summarize` (string) keys
    - `@settings(max_examples=100)`
    - **Validates: Requirements 5.5**
  - [ ]* 5.3 Write property test: LLM prompt includes all required context
    - **Property 7: LLM prompt includes all required context**
    - In `agent-core/tests/test_compare_product.py`: use Hypothesis to generate user demographics, item history, preferences, and available items, mock `call_bedrock_llm` to capture prompt, assert prompt contains string representations of all elements
    - `@settings(max_examples=100)`
    - **Validates: Requirements 5.4**

- [x] 6. Implement recommendation tool
  - [x] 6.1 Create `agent-core/tools/get_recommendation.py` with `@tool` decorated `get_recommendation(user_id: str, preference: str) -> str`
    - Port logic from `lambda/handler.py` `get_recommendation()`
    - Read `config.recommender_arn` — if None, return `"Recommender is not configured. Set RECOMMENDER_ARN."`
    - Call `personalize_runtime.get_recommendations(recommenderArn=..., userId=..., numResults=5)`
    - Call `get_user_info(user_id)` → DynamoDB `user_table`
    - Enrich with item history from `item_table`
    - Construct recommendation prompt and call `call_bedrock_llm(prompt)`
    - Return JSON: `{"items": [...], "summarize": "..."}`
    - Wrap in try/except for Personalize and DynamoDB errors
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.4_
  - [ ]* 6.2 Write property test: Recommendation tool returns structured output
    - **Property 5: Compare and Recommend tools return structured output**
    - In `agent-core/tests/test_recommendation.py`: use Hypothesis to generate valid inputs, mock Personalize, DynamoDB, Bedrock, assert returned JSON has `items` (list) and `summarize` (string) keys
    - `@settings(max_examples=100)`
    - **Validates: Requirements 6.6**
  - [ ]* 6.3 Write property test: Recommendation LLM prompt includes all required context
    - **Property 7: LLM prompt includes all required context**
    - In `agent-core/tests/test_recommendation.py`: use Hypothesis to generate user demographics, item history, preferences, and recommended items, mock `call_bedrock_llm` to capture prompt, assert prompt contains all elements
    - `@settings(max_examples=100)`
    - **Validates: Requirements 6.5**

- [x] 7. Checkpoint — Core tools complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement AgentCore entrypoint and Strands Agent
  - [x] 8.1 Create `agent-core/agent.py` with `BedrockAgentCoreApp` entrypoint and Strands Agent
    - Import `BedrockAgentCoreApp` from `bedrock_agentcore.runtime`
    - Load `Config` at module level (singleton)
    - Initialize Strands `Agent` with sales expert system prompt (search, compare, recommend, respond in customer's language) and all three tools
    - Configure model provider: `"bedrock/" + config.model_id`
    - Define `@app.entrypoint` async function `invoke(payload=None)`:
      - Extract `prompt` from payload (default: `"Hello! How can I help you today?"` if missing or None)
      - Invoke agent with prompt
      - Return `{"result": str(result)}`
    - Include `if __name__ == "__main__": app.run()`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 8.1_
  - [ ]* 8.2 Write property test: Entrypoint extracts prompt and returns result
    - **Property 3: Entrypoint extracts prompt and returns result**
    - In `agent-core/tests/test_entrypoint.py`: use Hypothesis to generate payload dicts with `prompt` key containing non-empty strings, mock the Strands Agent, assert agent is called with the prompt string and return dict has `result` key
    - `@settings(max_examples=100)`
    - **Validates: Requirements 2.3, 2.4**

- [x] 9. Implement error handling property tests
  - [ ]* 9.1 Write property test: Tool error handling returns descriptive messages
    - **Property 8: Tool error handling returns descriptive messages**
    - In `agent-core/tests/test_error_handling.py`: use Hypothesis to generate exception messages, mock external services (OpenSearch, DynamoDB, Bedrock, Personalize) to raise exceptions, assert each tool (`search_product`, `compare_product`, `get_recommendation`) returns a string containing a descriptive error message rather than raising an unhandled exception
    - `@settings(max_examples=100)`
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**

- [x] 10. Checkpoint — Agent entrypoint and error handling verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement CDK stack and infrastructure
  - [x] 11.1 Create `agent-core/cdk/infra_utils/agentcore_role.py` with AgentCore execution IAM role
    - Create function/class that builds an `iam.Role` assumed by `bedrock-agentcore.amazonaws.com`
    - Inline policies: ECR pull (`ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:GetAuthorizationToken`), CloudWatch logs (`/aws/bedrock-agentcore/runtimes/*`), X-Ray traces, Bedrock (`bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`), SSM (`ssm:GetParametersByPath` for `/agentcore/sales-agent/*`), DynamoDB (`dynamodb:Query`, `dynamodb:GetItem`), OpenSearch (`aoss:APIAccessAll`), Personalize (`personalize:GetRecommendations`)
    - _Requirements: 10.9_
  - [x] 11.2 Create `agent-core/cdk/infra_utils/build_trigger_lambda.py` Lambda handler for CloudFormation custom resource
    - On `Create`/`Update`: call `codebuild.start_build(projectName=...)`, poll `batch_get_builds()` until `buildStatus` is `SUCCEEDED` or `FAILED`
    - On `Delete`: no-op
    - Report result via cfn-response callback
    - Timeout: 15 minutes (accommodate Docker build time)
    - _Requirements: 10.10_
  - [x] 11.3 Create `agent-core/cdk/agentcore_stack.py` CDK stack with all infrastructure resources
    - ECR repository: `empty_on_delete=True`, `image_scan_on_push=True`, `RemovalPolicy.DESTROY`
    - S3 asset: package `agent-core/` directory for CodeBuild source input
    - CodeBuild project: ARM64 via `LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0`, `ComputeType.LARGE`, privileged mode, S3 source from asset, inline buildspec via `BuildSpec.from_object()` (NO separate buildspec.yml)
    - Lambda custom resource: triggers CodeBuild and waits for completion
    - AgentCore execution role: from `agentcore_role.py`
    - `bedrockagentcore.CfnRuntime`: `container_uri` from ECR, `network_configuration` (PUBLIC default or VPC mode), `protocol_configuration="HTTP"`, `environment_variables`; depends on Lambda custom resource
    - SSM parameters under `/agentcore/sales-agent/` prefix: `aoss_collection_id`, `aoss_region`, `item_table_name`, `user_table_name`, `recommender_arn`
    - CfnOutputs: `RuntimeArn`, `RuntimeId`, `EcrRepositoryUri`
    - CDK context params: `aoss-endpoint`, `aoss-region`, `item-table-name`, `user-table-name`, `recommender-arn`, `network-mode`, `subnets`, `security-groups`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.7, 10.8, 10.10, 11.1, 11.2, 11.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_
  - [x] 11.4 Create `agent-core/cdk/app.py` CDK app entry point
    - Instantiate `AgentCoreStack` with app context
    - _Requirements: 10.1_
  - [ ]* 11.5 Write property test: CfnRuntime network configuration matches input
    - **Property 9: CfnRuntime network configuration matches input**
    - In `agent-core/tests/test_cdk_stack.py`: use Hypothesis to generate valid network modes (`PUBLIC`/`PRIVATE`) and corresponding subnet/security-group values, synth the stack, assert CfnRuntime `network_configuration` matches input
    - `@settings(max_examples=100)`
    - **Validates: Requirements 11.3**
  - [ ]* 11.6 Write property test: SSM parameters share consistent prefix
    - **Property 10: SSM parameters share consistent prefix**
    - In `agent-core/tests/test_cdk_stack.py`: synth the stack, assert all SSM parameter paths start with `/agentcore/sales-agent/`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 12.5**

- [x] 12. Implement Dockerfile and requirements.txt
  - [x] 12.1 Create `agent-core/Dockerfile` following official AgentCore pattern
    - Single-stage `python:3.12-slim` from public ECR
    - Install deps from `requirements.txt` and `aws-opentelemetry-distro==0.10.1`
    - Non-root user `bedrock_agentcore` (uid 1000)
    - Expose ports 8080 and 8000
    - Healthcheck on port 8080 (`/ping`)
    - `CMD ["opentelemetry-instrument", "python", "agent.py"]`
    - _Requirements: 10.6_
  - [x] 12.2 Create `agent-core/requirements.txt` for Docker build compatibility
    - Generate from `pyproject.toml` via `uv pip compile pyproject.toml -o requirements.txt`
    - _Requirements: 10.6_

- [x] 13. Checkpoint — CDK stack and Docker verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement deploy script
  - [x] 14.1 Create `agent-core/deploy.sh` shell script
    - `set -euo pipefail` for strict error handling
    - Accept CLI arguments: `--aoss-endpoint` (required), `--item-table`, `--user-table`, `--recommender-arn`, `--network-mode`, `--subnets`, `--security-groups`, `--region`
    - Validate `--aoss-endpoint` is provided (exit with error if missing)
    - Build CDK context args string from CLI parameters
    - Run `cdk deploy AgentCoreStack` with context parameters
    - Extract `RuntimeArn` and `EcrRepositoryUri` from CDK outputs
    - Print deployment summary with Runtime ARN, ECR URI, and test invoke command
    - Print note reminding user to call `update_agent_runtime` for subsequent image updates
    - Exit non-zero with descriptive message on any step failure
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 11.4_

- [x] 15. Implement Chat CLI
  - [x] 15.1 Create `agent-core/chat_cli.py` interactive chat script
    - Accept `--endpoint` arg or read `AGENTCORE_ENDPOINT` env var (CLI arg takes precedence)
    - Accept optional `--user-id` arg
    - Display welcome message, enter REPL input loop
    - Send `{"prompt": "<message>", "user_id": "<id>"}` payload to endpoint via HTTP POST
    - Display agent response
    - Exit gracefully on `exit` or `quit` with farewell message
    - Handle connection errors with descriptive message and retry prompt
    - Print usage and exit if no endpoint provided
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8_
  - [ ]* 15.2 Write property test: Chat CLI constructs correct payload
    - **Property 11: Chat CLI constructs correct payload**
    - In `agent-core/tests/test_chat_cli.py`: use Hypothesis to generate message strings and optional user_id strings, assert constructed payload has `prompt` equal to message, and `user_id` present only when provided
    - `@settings(max_examples=100)`
    - **Validates: Requirements 15.4, 15.8**
  - [ ]* 15.3 Write property test: Chat CLI resolves endpoint with precedence
    - **Property 12: Chat CLI resolves endpoint with precedence**
    - In `agent-core/tests/test_chat_cli.py`: use Hypothesis to generate endpoint strings, test with arg only, env var only, and both (arg takes precedence)
    - `@settings(max_examples=100)`
    - **Validates: Requirements 15.2**

- [x] 16. Create README
  - [x] 16.1 Create `agent-core/README.md` with project documentation
    - Project overview and architecture
    - Prerequisites: `uv`, Docker, AWS CLI, CDK
    - Setup steps: `uv sync`, environment configuration
    - Local development: `agentcore dev`, `agentcore invoke --dev '{"prompt": "..."}'`
    - Deployment via `deploy.sh` with all CLI arguments documented
    - Updating the runtime after subsequent image rebuilds: document `update_agent_runtime` workflow (call via AWS CLI or SDK after CodeBuild pushes new image, DEFAULT endpoint auto-updates to latest version)
    - Chat CLI usage: `python chat_cli.py --endpoint <url> --user-id <id>`
    - Running tests: `uv run pytest`
    - _Requirements: 1.4, 8.1, 8.2, 8.3, 8.4_

- [x] 17. Final checkpoint — All tests pass, integration verified
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate the 12 correctness properties from the design document
- External services (Bedrock, OpenSearch, DynamoDB, Personalize) are mocked in all tests
- The existing `lambda/handler.py` serves as the reference implementation for porting tool logic
- CDK requires `aws-cdk-lib>=2.220.0` for `aws_bedrockagentcore` module
- No separate `buildspec.yml` — buildspec is inline in CDK via `BuildSpec.from_object()`
- No `agentcore configure/launch` needed — `CfnRuntime` handles deployment atomically
