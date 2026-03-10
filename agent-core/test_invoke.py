#!/usr/bin/env python3
"""Quick test script to invoke the deployed AgentCore runtime via WebSocket."""

import asyncio
import json
import sys

import boto3
import websockets
from bedrock_agentcore.runtime import AgentCoreRuntimeClient

RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:718498700052:runtime/agentcore_sales_agent-3iEHtZ9xPY"
REGION = "us-east-1"
PROFILE = "ray-testing"


async def invoke(prompt: str, timeout: int = 120) -> None:
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    client = AgentCoreRuntimeClient(region=REGION, session=session)
    url = client.generate_presigned_url(runtime_arn=RUNTIME_ARN, endpoint_name="DEFAULT")

    print(f"Connecting to runtime (timeout={timeout}s)...")
    try:
        async with websockets.connect(url, open_timeout=timeout, close_timeout=10) as ws:
            payload = json.dumps({"prompt": prompt})
            await ws.send(payload)
            print("Message sent. Waiting for response...\n")

            async for msg in ws:
                data = json.loads(msg)
                # Print whatever comes back
                if "result" in data:
                    print(f"Agent: {data['result']}")
                    break
                elif "error" in data:
                    print(f"Error: {data['error']}")
                    break
                else:
                    print(f"[raw] {json.dumps(data)[:300]}")
    except websockets.exceptions.InvalidStatus as exc:
        print(f"HTTP {exc.response.status_code} — runtime may be cold-starting.")
        print("Try again in 30-60 seconds.")
    except asyncio.TimeoutError:
        print("Timed out waiting for response.")
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Hello, what can you help me with?"
    asyncio.run(invoke(prompt))
