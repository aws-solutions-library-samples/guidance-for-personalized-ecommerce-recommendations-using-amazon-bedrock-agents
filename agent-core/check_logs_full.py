#!/usr/bin/env python3
"""Check CloudWatch logs - get ALL events with full detail."""
import boto3
import json
from datetime import datetime

session = boto3.Session(profile_name="ray-testing", region_name="us-east-1")
logs = session.client("logs")

log_group = "/aws/bedrock-agentcore/runtimes/agentcore_sales_agent-3iEHtZ9xPY-DEFAULT"

# Get all streams
streams = logs.describe_log_streams(
    logGroupName=log_group, orderBy="LastEventTime", descending=True, limit=5
)

for stream in streams["logStreams"]:
    sname = stream["logStreamName"]
    print(f"\n=== Stream: {sname} ===")
    
    events = logs.get_log_events(
        logGroupName=log_group, logStreamName=sname, limit=50, startFromHead=False
    )
    
    for i, event in enumerate(events["events"][-30:]):
        msg = event["message"]
        try:
            data = json.loads(msg)
            sev = data.get("severityText", "")
            body = data.get("body", "")
            if isinstance(body, dict):
                body = body.get("stringValue", json.dumps(body))
            attrs = data.get("attributes", {})
            exc_info = ""
            if isinstance(attrs, dict):
                for key, val in attrs.items():
                    if "exception" in key.lower() or "error" in key.lower():
                        exc_info += f" {key}={json.dumps(val)[:200]}"
            elif isinstance(attrs, list):
                for attr in attrs:
                    if isinstance(attr, dict):
                        key = attr.get("key", "")
                        if "exception" in key.lower() or "error" in key.lower():
                            exc_info += f" {key}={json.dumps(attr.get('value', ''))[:200]}"
            
            ts = data.get("timeUnixNano", "")
            if ts:
                t = datetime.fromtimestamp(int(ts) / 1e9)
                ts_str = t.strftime("%H:%M:%S")
            else:
                ts_str = "?"
            
            line = f"[{ts_str}][{sev}] {str(body)[:300]}"
            if exc_info:
                line += f"\n  EXCEPTION:{exc_info}"
            print(line)
        except json.JSONDecodeError:
            print(f"[RAW] {msg[:300]}")
