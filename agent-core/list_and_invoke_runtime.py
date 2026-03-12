#!/usr/bin/env python3
"""
List AgentCore runtimes and invoke one.
"""

import boto3
import json
import os

# Set AWS profile
os.environ['AWS_PROFILE'] = 'ray-testing'

print("=" * 60)
print("Listing AgentCore Runtimes")
print("=" * 60)

try:
    # Create bedrock-agentcore-control client
    control_client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
    
    # List agent runtimes
    response = control_client.list_agent_runtimes()
    
    print(f"\nFound {len(response.get('agentRuntimes', []))} agent runtime(s):\n")
    
    for runtime in response.get('agentRuntimes', []):
        print(f"Name: {runtime.get('agentRuntimeName')}")
        print(f"  ARN: {runtime.get('agentRuntimeArn')}")
        print(f"  ID: {runtime.get('agentRuntimeId')}")
        print(f"  Version: {runtime.get('agentRuntimeVersion')}")
        print(f"  Status: {runtime.get('status')}")
        print(f"  Description: {runtime.get('description')}")
        print(f"  Last Updated: {runtime.get('lastUpdatedAt')}")
        print()
    
    # If we found runtimes, try to invoke the first one
    if response.get('agentRuntimes'):
        runtime_arn = response['agentRuntimes'][0]['agentRuntimeArn']
        
        print("=" * 60)
        print(f"Invoking Runtime: {runtime_arn}")
        print("=" * 60)
        
        # Create bedrock-agentcore client for invocation
        agentcore_client = boto3.client('bedrock-agentcore', region_name='us-east-1')
        
        # Prepare payload
        payload = json.dumps({"prompt": "Hello, can you help me find a blue dress?"}).encode()
        
        # Invoke the agent runtime (session ID must be at least 33 characters)
        import uuid
        session_id = f"test-session-{uuid.uuid4()}"
        
        invoke_response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        print(f"\nInvocation Response:")
        print(f"  Status Code: {invoke_response.get('statusCode')}")
        print(f"  Content Type: {invoke_response.get('contentType')}")
        print(f"  Runtime Session ID: {invoke_response.get('runtimeSessionId')}")
        
        # Process streaming response
        if "text/event-stream" in invoke_response.get("contentType", ""):
            print("\nAgent Response (streaming):")
            print("-" * 60)
            
            content = []
            for chunk in invoke_response["response"].iter_lines(chunk_size=10):
                if chunk:
                    line = chunk.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                    print(line)
                    content.append(line)
            
            print("-" * 60)
            print(f"\nComplete response: {len(content)} chunks received")
            
        elif invoke_response.get("contentType") == "application/json":
            print("\nAgent Response (JSON):")
            print("-" * 60)
            
            content = []
            for chunk in invoke_response.get("response", []):
                content.append(chunk.decode('utf-8'))
            
            response_text = ''.join(content)
            print(json.dumps(json.loads(response_text), indent=2))
            print("-" * 60)
        else:
            print(f"\nRaw response: {invoke_response}")
    
    else:
        print("No agent runtimes found.")
        print("\nYou may need to create an agent runtime first using:")
        print("  aws bedrock-agentcore-control create-agent-runtime ...")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
