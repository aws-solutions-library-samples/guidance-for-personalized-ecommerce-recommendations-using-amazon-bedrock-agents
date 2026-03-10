#!/usr/bin/env python3
"""Test invoking the AgentCore runtime via HTTP (through WebSocket transport)."""
import asyncio
import json
import sys
import boto3
import websockets
from bedrock_agentcore.runtime import AgentCoreRuntimeClient

RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:718498700052:runtime/agentcore_sales_agent-3iEHtZ9xPY"
REGION = "us-east-1"
PROFILE = "ray-testing"


async def invoke(prompt: str) -> None:
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    client = AgentCoreRuntimeClient(region=REGION, session=session)
    url = client.generate_presigned_url(runtime_arn=RUNTIME_ARN, endpoint_name="DEFAULT")

    print(f"Connecting...")
    try:
        async with websockets.connect(url, open_timeout=120, close_timeout=30, ping_interval=30) as ws:
            payload = json.dumps({"prompt": prompt})
            await ws.send(payload)
            print(f"Sent: {prompt}")
            print("Waiting for response (may take 30-60s for cold start + LLM call)...\n")

            try:
                response = await asyncio.wait_for(ws.recv(), timeout=120)
                data = json.loads(response)
                if "result" in data:
                    print(f"Agent: {data['result']}")
                elif "error" in data:
                    print(f"Error: {data['error']}")
                else:
                    print(f"Raw: {json.dumps(data, indent=2)[:500]}")
            except asyncio.TimeoutError:
                print("Timed out waiting for response (120s)")

    except websockets.exceptions.InvalidStatus as exc:
        print(f"HTTP {exc.response.status_code}")
        body = getattr(exc.response, "body", b"")
        if body:
            print(f"Body: {body[:500]}")
    except websockets.exceptions.ConnectionClosedError as exc:
        print(f"Connection closed: code={exc.code} reason={exc.reason}")
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Hello"
    asyncio.run(invoke(prompt))
