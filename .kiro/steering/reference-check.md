---
inclusion: auto
---

# Reference Check Before Task Execution

## Rule
Before executing any spec task, always fetch the latest version of the reference implementation from the upstream repository to ensure the implementation stays aligned with the latest patterns and APIs.

## Reference Repository
- URL: https://github.com/lubao/guidance-for-personalized-ecommerce-recommendations-using-amazon-bedrock-agents
- Key file: `agent-core/cli/sales_agent_cli.py`
- Streaming module: `agent-core/cli/streaming.py`

## Process
1. Use `webFetch` to retrieve the raw content from the reference repo before starting a task
2. Compare the reference patterns with the current implementation plan
3. If the reference has diverged, note the differences and adapt accordingly
4. Proceed with task execution using the latest patterns
