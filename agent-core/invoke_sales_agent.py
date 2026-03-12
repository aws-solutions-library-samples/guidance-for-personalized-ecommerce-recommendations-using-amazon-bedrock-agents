#!/usr/bin/env python3
"""
Invoke the sales_strands_agent runtime using Bedrock AgentCore API.
"""

import boto3
import json
import os
import uuid

# Set AWS profile
os.environ['AWS_PROFILE'] = 'ray-testing'

# Runtime ARN for sales_strands_agent
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:718498700052:runtime/sales_strands_agent-pTlczKAZuV"

print("=" * 60)
print("Invoking Sales Strands Agent Runtime")
print("=" * 60)
print(f"Runtime ARN: {RUNTIME_ARN}")
print()

try:
    # Create bedrock-agentcore client for invocation
    agentcore_client = boto3.client('bedrock-agentcore', region_name='us-east-1')
    
    # Prepare payload
    payload = json.dumps({
        "prompt": "Hello, can you help me find a blue dress?"
    }).encode()
    
    # Generate session ID (must be at least 33 characters)
    session_id = f"test-session-{uuid.uuid4()}"
    
    print(f"Session ID: {session_id}")
    print(f"Prompt: Hello, can you help me find a blue dress?")
    print()
    
    # Invoke the agent runtime
    invoke_response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload
    )
    
    print(f"Invocation Response:")
    print(f"  Status Code: {invoke_response.get('statusCode')}")
    print(f"  Content Type: {invoke_response.get('contentType')}")
    print(f"  Runtime Session ID: {invoke_response.get('runtimeSessionId')}")
    print()
    
    # Process streaming response
    if "text/event-stream" in invoke_response.get("contentType", ""):
        print("Agent Response (streaming):")
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
        print("Agent Response (JSON):")
        print("-" * 60)
        
        content = []
        for chunk in invoke_response.get("response", []):
            content.append(chunk.decode('utf-8'))
        
        response_text = ''.join(content)
        print(json.dumps(json.loads(response_text), indent=2))
        print("-" * 60)
    else:
        print(f"Raw response: {invoke_response}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
