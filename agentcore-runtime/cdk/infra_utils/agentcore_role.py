"""AgentCore execution IAM role for bedrock-agentcore.amazonaws.com."""

from aws_cdk import aws_iam as iam
from constructs import Construct


def create_agentcore_role(scope: Construct, id: str) -> iam.Role:
    """Create an IAM role for AgentCore Runtime execution.

    The role is assumed by bedrock-agentcore.amazonaws.com and grants
    permissions for ECR pull, CloudWatch logs, X-Ray, Bedrock model
    invocation, SSM parameter read, DynamoDB read, OpenSearch access,
    and Personalize access.

    Args:
        scope: The CDK construct scope.
        id: The construct ID for the role.

    Returns:
        The configured IAM Role.
    """
    role = iam.Role(
        scope,
        id,
        assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
        description="Execution role for AgentCore Sales Agent runtime",
    )

    # ECR pull permissions
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer",
                "ecr:GetAuthorizationToken",
            ],
            resources=["*"],
        )
    )

    # CloudWatch Logs
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=[
                "arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/runtimes/*",
            ],
        )
    )

    # X-Ray tracing
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
            ],
            resources=["*"],
        )
    )

    # Bedrock model invocation
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=["*"],
        )
    )

    # Bedrock AgentCore Memory Service
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["bedrock-agentcore:memory:*"],
            resources=["*"],
        )
    )

    # SSM Parameter Store read
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["ssm:GetParametersByPath"],
            resources=[
                "arn:aws:ssm:*:*:parameter/agentcore/sales-agent/*",
            ],
        )
    )

    # DynamoDB read access
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "dynamodb:Query",
                "dynamodb:GetItem",
            ],
            resources=["*"],
        )
    )

    # OpenSearch Serverless access
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["aoss:APIAccessAll"],
            resources=["*"],
        )
    )

    # Amazon Personalize access
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["personalize:GetRecommendations"],
            resources=["*"],
        )
    )

    return role
