#!/usr/bin/env python3
"""Check CloudWatch logs for the AgentCore runtime."""
import boto3
import json

session = boto3.Session(profile_name="ray-testing", region_name="us-east-1")
logs = session.client("logs")

log_group = "/aws/bedrock-agentcore/runtimes/agentcore_sales_agent-3iEHtZ9xPY-DEFAULT"

events = logs.get_log_events(
    logGroupName=log_group,
    logStreamName="otel-rt-logs",
    limit=20,
    startFromHead=False,
)

print(f"Total events: {len(events['events'])}")
for i, event in enumerate(events["events"]):
    data = json.loads(event["message"])
    sev = data.get("severityText", "?")
    body = data.get("body", "")
    if isinstance(body, dict):
        body = body.get("stringValue", json.dumps(body))
    ts = data.get("timeUnixNano", "")
    # Convert nanoseconds to readable time
    if ts:
        from datetime import datetime
        t = datetime.fromtimestamp(int(ts) / 1e9)
        ts_str = t.strftime("%H:%M:%S")
    else:
        ts_str = "?"
    print(f"[{ts_str}][{sev}] {str(body)[:300]}")
