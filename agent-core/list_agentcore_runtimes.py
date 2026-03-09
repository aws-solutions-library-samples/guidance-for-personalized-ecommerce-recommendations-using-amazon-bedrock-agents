#!/usr/bin/env python3
"""
Script to list AgentCore runtimes using boto3.
"""

import boto3
import json

# Try to create bedrock-agentcore client
try:
    client = boto3.client('bedrock-agentcore', region_name='us-east-1')
    print("✓ bedrock-agentcore client created successfully")
    
    # Try to list operations
    print("\nAvailable operations:")
    operations = [op for op in dir(client) if not op.startswith('_')]
    for op in sorted(operations):
        print(f"  - {op}")
    
    # Try to list agent runtime endpoints
    if hasattr(client, 'list_agent_runtime_endpoints'):
        print("\nListing agent runtime endpoints...")
        response = client.list_agent_runtime_endpoints()
        print(json.dumps(response, indent=2, default=str))
    else:
        print("\nlist_agent_runtime_endpoints method not found")
        
except Exception as e:
    print(f"Error: {e}")
    print("\nTrying bedrock-agentcore-control...")
    
    try:
        client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
        print("✓ bedrock-agentcore-control client created successfully")
        
        # Try to list operations
        print("\nAvailable operations:")
        operations = [op for op in dir(client) if not op.startswith('_')]
        for op in sorted(operations):
            print(f"  - {op}")
            
    except Exception as e2:
        print(f"Error: {e2}")
        print("\nThe bedrock-agentcore service may not be available in this region or boto3 version.")
