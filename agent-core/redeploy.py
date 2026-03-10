#!/usr/bin/env python3
"""Trigger CodeBuild, wait, then update runtime."""
import time
import boto3

session = boto3.Session(profile_name="ray-testing", region_name="us-east-1")
cb = session.client("codebuild")
ac = session.client("bedrock-agentcore-control")

PROJECT = "AgentCoreCodeBuild9B052DED-YEfb1YLu9TkG"
RUNTIME_ID = "agentcore_sales_agent-3iEHtZ9xPY"

# Step 1: Trigger build
print("=== Step 1: Triggering CodeBuild ===")
resp = cb.start_build(projectName=PROJECT)
build_id = resp["build"]["id"]
print(f"Build: {build_id}")

while True:
    time.sleep(10)
    result = cb.batch_get_builds(ids=[build_id])
    b = result["builds"][0]
    status = b["buildStatus"]
    phase = b.get("currentPhase", "?")
    print(f"  {status} / {phase}")
    if status != "IN_PROGRESS":
        break

if status != "SUCCEEDED":
    print(f"Build FAILED: {status}")
    exit(1)

# Step 2: Update runtime
print("\n=== Step 2: Updating runtime ===")
rt = ac.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
print(f"Current version: {rt['agentRuntimeVersion']}")

ac.update_agent_runtime(
    agentRuntimeId=RUNTIME_ID,
    agentRuntimeArtifact=rt["agentRuntimeArtifact"],
    roleArn=rt["roleArn"],
    networkConfiguration=rt["networkConfiguration"],
    protocolConfiguration={"serverProtocol": "HTTP"},
    environmentVariables=rt.get("environmentVariables", {}),
)

while True:
    time.sleep(10)
    rt = ac.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
    status = rt["status"]
    ver = rt["agentRuntimeVersion"]
    print(f"  {status} v{ver}")
    if status in ("READY", "FAILED"):
        break

print(f"\nDone. Runtime v{ver} is {status}.")
