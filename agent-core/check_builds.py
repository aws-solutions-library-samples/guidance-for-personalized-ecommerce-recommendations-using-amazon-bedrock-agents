#!/usr/bin/env python3
"""Check recent CodeBuild builds."""
import boto3

session = boto3.Session(profile_name="ray-testing", region_name="us-east-1")
cb = session.client("codebuild")

project = "AgentCoreCodeBuild9B052DED-YEfb1YLu9TkG"
builds = cb.list_builds_for_project(projectName=project, sortOrder="DESCENDING")

if builds["ids"]:
    details = cb.batch_get_builds(ids=builds["ids"][:5])
    for b in details["builds"]:
        print(f"{b['id'][-12:]}  status={b['buildStatus']:12s}  started={b['startTime']}  source={b['source']['location'][:80]}")
else:
    print("No builds found")
