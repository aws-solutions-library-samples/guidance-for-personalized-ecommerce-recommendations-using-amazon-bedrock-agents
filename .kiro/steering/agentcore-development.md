---
inclusion: auto
---

# AgentCore Development Guidelines

## File Operations
- Never use bash commands (cat, echo, sed, tee, etc.) to read or write files. Use the built-in file read/write tools instead.
- Use `readFile`, `readCode`, or `readMultipleFiles` for reading files.
- Use `fsWrite`, `fsAppend`, `strReplace`, or `editCode` for writing/editing files.

## Documentation First
- Before implementing any task, always check the latest documentation using the `aws-agentcore` power, `strands` power, and `aws-infrastructure-as-code` power.
- Activate the relevant power and read steering files or use MCP tools to get up-to-date API references, patterns, and examples.
- This applies to AgentCore Runtime APIs, Strands Agents SDK, AWS CDK constructs, and any AWS service integrations.
