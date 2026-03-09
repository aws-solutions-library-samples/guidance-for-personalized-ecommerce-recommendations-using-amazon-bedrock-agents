#!/usr/bin/env python3
"""
Test script to invoke the AgentCore runtime via HTTP.

Since the ALB is internal-only, this script must be run from within the VPC
or from a machine that has network access to the VPC (e.g., via VPN or bastion host).
"""

import json
import sys
import requests
from datetime import datetime

# Runtime endpoint (internal ALB)
RUNTIME_ENDPOINT = "http://internal-Runtim-Servi-L4JAqyIzWWYb-2045103450.us-east-1.elb.amazonaws.com"

def invoke_runtime(message: str, actor_id: str = "test-user", session_id: str = None):
    """
    Invoke the AgentCore runtime with a message.
    
    Args:
        message: User message to send to the agent
        actor_id: User/actor identifier for personalization
        session_id: Session ID for conversation continuity
    """
    # Generate session ID if not provided
    if not session_id:
        session_id = f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Build payload
    payload = {
        "prompt": message,
        "actor_id": actor_id,
        "session_id": session_id
    }
    
    print(f"Invoking runtime at: {RUNTIME_ENDPOINT}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        # The BedrockAgentCoreApp exposes the entrypoint at /invocations
        invoke_url = f"{RUNTIME_ENDPOINT}/invocations"
        
        print(f"Sending POST request to: {invoke_url}")
        print()
        
        # Make POST request
        response = requests.post(
            invoke_url,
            json=payload,
            timeout=60,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            stream=True
        )
        
        # Check for HTTP errors
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print("Agent Response:")
        print("=" * 60)
        
        # Stream response
        for line in response.iter_lines():
            if line:
                try:
                    # Try to parse as JSON
                    event = json.loads(line.decode('utf-8'))
                    print(json.dumps(event, indent=2))
                except json.JSONDecodeError:
                    # If not JSON, print as text
                    print(line.decode('utf-8'))
        
        print("=" * 60)
        print("\n✓ Invocation successful!")
        return True
        
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Connection failed - {e}")
        print("\nThis is expected if running from outside the VPC.")
        print("The ALB is internal-only for security.")
        print("\nTo test the runtime, you need to:")
        print("  1. Run this script from an EC2 instance in the VPC")
        print("  2. Use AWS Systems Manager Session Manager")
        print("  3. Set up a VPN connection to the VPC")
        return False
        
    except requests.exceptions.Timeout as e:
        print(f"Error: Request timed out - {e}")
        return False
        
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    # Test message
    message = "Hello, can you help me find a blue dress?"
    
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    
    print("Testing AgentCore Runtime Invocation")
    print("=" * 60)
    print()
    
    success = invoke_runtime(message)
    
    sys.exit(0 if success else 1)
