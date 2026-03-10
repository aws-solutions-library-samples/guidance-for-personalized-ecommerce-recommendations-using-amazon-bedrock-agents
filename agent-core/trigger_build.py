#!/usr/bin/env python3
"""Trigger a new CodeBuild and wait for completion."""
import time
import boto3

session = boto3.Session(profile_name="ray-testing", region_name="us-east-1")
cb = session.client("codebuild")

project = "AgentCoreCodeBuild9B052DED-YEfb1YLu9TkG"

print(f"Starting build for {project}...")
resp = cb.start_build(projectName=project)
build_id = resp["build"]["id"]
print(f"Build ID: {build_id}")

while True:
    time.sleep(10)
    result = cb.batch_get_builds(ids=[build_id])
    build = result["builds"][0]
    status = build["buildStatus"]
    phase = build.get("currentPhase", "?")
    print(f"  Status: {status}  Phase: {phase}")
    if status != "IN_PROGRESS":
        break

print(f"\nFinal status: {status}")
