#!/usr/bin/env python3
"""Update the AgentCore runtime to pick up the new container image."""
import time
import boto3

session = boto3.Session(profile_name="ray-testing", region_name="us-east-1")
client = session.client("bedrock-agentcore-control")

runtime_id = "agentcore_sales_agent-3iEHtZ9xPY"

# Get current runtime config
rt = client.get_agent_runtime(agentRuntimeId=runtime_id)
print(f"Current version: {rt['agentRuntimeVersion']}")
print(f"Current status: {rt['status']}")

# Update runtime to force redeployment with latest image
print("\nUpdating runtime...")
resp = client.update_agent_runtime(
    agentRuntimeId=runtime_id,
    agentRuntimeArtifact=rt["agentRuntimeArtifact"],
    roleArn=rt["roleArn"],
    networkConfiguration=rt["networkConfiguration"],
    protocolConfiguration={"serverProtocol": "HTTP"},
    environmentVariables=rt.get("environmentVariables", {}),
)
print(f"Update response status: {resp['status']}")

# Wait for READY
print("Waiting for runtime to become READY...")
while True:
    time.sleep(10)
    rt = client.get_agent_runtime(agentRuntimeId=runtime_id)
    status = rt["status"]
    version = rt["agentRuntimeVersion"]
    print(f"  Status: {status}  Version: {version}")
    if status == "READY":
        print("\nRuntime is READY with updated image.")
        break
    if status in ("FAILED", "DELETE_FAILED"):
        print(f"\nRuntime update FAILED: {status}")
        break
