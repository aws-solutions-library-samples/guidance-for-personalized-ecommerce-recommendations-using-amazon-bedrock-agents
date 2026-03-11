"""Lambda handler for CloudFormation custom resource that updates AOSS data access policy.

On Create/Update: adds the execution role ARN to the AOSS data access policy principals.
On Delete: removes the execution role ARN from the policy.
Reports result via cfn-response HTTPS callback.
"""

import boto3
import json
import urllib.request

aoss = boto3.client("opensearchserverless")


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
    """Add or remove the execution role from the AOSS data access policy."""
    try:
        request_type = event["RequestType"]
        policy_name = event["ResourceProperties"]["PolicyName"]
        role_arn = event["ResourceProperties"]["RoleArn"]

        # Get current policy
        resp = aoss.get_access_policy(name=policy_name, type="data")
        detail = resp["accessPolicyDetail"]
        policy = detail["policy"]
        version = detail["policyVersion"]

        if request_type in ("Create", "Update"):
            # Add role if not already present
            if role_arn not in policy[0]["Principal"]:
                policy[0]["Principal"].append(role_arn)
                aoss.update_access_policy(
                    name=policy_name,
                    type="data",
                    policyVersion=version,
                    policy=json.dumps(policy),
                )
            send_response(event, context, "SUCCESS", f"Role added to {policy_name}")

        elif request_type == "Delete":
            # Remove role if present
            if role_arn in policy[0]["Principal"]:
                policy[0]["Principal"].remove(role_arn)
                aoss.update_access_policy(
                    name=policy_name,
                    type="data",
                    policyVersion=version,
                    policy=json.dumps(policy),
                )
            send_response(event, context, "SUCCESS", f"Role removed from {policy_name}")

    except Exception as e:
        send_response(event, context, "FAILED", str(e))
