"""Lambda handler for CloudFormation custom resource that triggers CodeBuild.

On Create/Update: starts a CodeBuild build and polls until completion.
On Delete: no-op, sends SUCCESS immediately.
Reports result via cfn-response HTTPS callback.
Timeout: 15 minutes (to accommodate Docker build time).
"""

import boto3
import json
import time
import urllib.request

codebuild = boto3.client("codebuild")


def send_response(event, context, status, reason=""):
    """Send a response to the CloudFormation custom resource callback URL."""
    body = json.dumps({
        "Status": status,
        "Reason": reason,
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
    })

    request = urllib.request.Request(
        url=event["ResponseURL"],
        data=body.encode("utf-8"),
        method="PUT",
    )
    request.add_header("Content-Type", "")
    request.add_header("Content-Length", str(len(body)))

    urllib.request.urlopen(request)


def handler(event, context):
    """CloudFormation custom resource handler for triggering CodeBuild builds."""
    try:
        request_type = event["RequestType"]

        # On Delete, nothing to do
        if request_type == "Delete":
            send_response(event, context, "SUCCESS", "Delete complete")
            return

        # On Create/Update, trigger CodeBuild and wait for completion
        project_name = event["ResourceProperties"]["ProjectName"]

        response = codebuild.start_build(projectName=project_name)
        build_id = response["build"]["id"]

        # Poll until build completes
        while True:
            time.sleep(30)
            builds_response = codebuild.batch_get_builds(ids=[build_id])
            build = builds_response["builds"][0]
            build_status = build["buildStatus"]

            if build_status == "SUCCEEDED":
                send_response(event, context, "SUCCESS", "Build succeeded")
                return

            if build_status in ("FAILED", "STOPPED"):
                send_response(
                    event, context, "FAILED",
                    f"Build {build_status}: {build_id}",
                )
                return

            # Still IN_PROGRESS, continue polling

    except Exception as e:
        send_response(event, context, "FAILED", str(e))
