"""CDK stack for AgentCore Sales Agent infrastructure.

Provisions ECR, CodeBuild (S3 asset source), Lambda custom resource build trigger,
CfnRuntime, SSM parameters, AgentCore execution IAM role, and updates the AOSS
data access policy to grant the new role access.
"""

import os

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    CustomResource,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_s3_assets as s3_assets,
    aws_lambda as lambda_,
    aws_bedrockagentcore as bedrockagentcore,
)
from constructs import Construct
from cdk.infra_utils.agentcore_role import create_agentcore_role


class AgentCoreStack(Stack):
    """CDK stack provisioning the full AgentCore Runtime atomically."""

    def __init__(self, scope: Construct, construct_id: str, *, env_name: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Read CDK context parameters ---
        aoss_endpoint = self.node.try_get_context("aoss-endpoint")
        aoss_region = self.node.try_get_context("aoss-region") or self.region
        aoss_data_policy_name = self.node.try_get_context("aoss-data-policy-name") or ""
        item_table_name = self.node.try_get_context("item-table-name") or "item_table"
        user_table_name = self.node.try_get_context("user-table-name") or "user_table"
        recommender_arn = self.node.try_get_context("recommender-arn") or ""
        model_id = self.node.try_get_context("model-id") or "us.anthropic.claude-sonnet-4-20250514-v1:0"
        network_mode = self.node.try_get_context("network-mode") or "PUBLIC"
        subnets = self.node.try_get_context("subnets") or ""
        security_groups = self.node.try_get_context("security-groups") or ""
        env_name = env_name or self.node.try_get_context("env-name") or "production"
        memory_id = self.node.try_get_context("memory-id") or ""

        # --- 1. ECR Repository ---
        ecr_repo = ecr.Repository(
            self,
            f"AgentCoreEcrRepo-{env_name}",
            empty_on_delete=True,
            image_scan_on_push=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- 2. S3 Asset — package agentcore-runtime/ directory ---
        agent_core_dir = os.path.join(os.path.dirname(__file__), "..")
        source_asset = s3_assets.Asset(
            self,
            "AgentCoreSourceAsset",
            path=agent_core_dir,
            exclude=[
                ".venv",
                "__pycache__",
                "*.pyc",
                ".env",
                "cdk-outputs.json",
                "cdk.out",
                "tests",
                ".cdkignore",
                "deploy.sh",
            ],
        )

        # --- 3. CodeBuild Project — ARM64 native Docker build ---
        codebuild_project = codebuild.Project(
            self,
            "AgentCoreCodeBuild",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
                compute_type=codebuild.ComputeType.LARGE,
                privileged=True,
            ),
            source=codebuild.Source.s3(
                bucket=source_asset.bucket,
                path=source_asset.s3_object_key,
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REPO_URI",
                        ],
                    },
                    "build": {
                        "commands": [
                            "docker build -t $REPO_URI:latest .",
                        ],
                    },
                    "post_build": {
                        "commands": [
                            "docker push $REPO_URI:latest",
                        ],
                    },
                },
            }),
            environment_variables={
                "REPO_URI": codebuild.BuildEnvironmentVariable(
                    value=ecr_repo.repository_uri,
                ),
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(
                    value=self.region,
                ),
            },
        )

        # Grant CodeBuild permission to push to ECR
        ecr_repo.grant_pull_push(codebuild_project)

        # --- 4. Lambda Custom Resource — triggers CodeBuild and waits ---
        infra_utils_dir = os.path.join(os.path.dirname(__file__), "infra_utils")
        trigger_fn = lambda_.Function(
            self,
            "BuildTriggerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="build_trigger_lambda.handler",
            code=lambda_.Code.from_asset(infra_utils_dir),
            timeout=Duration.minutes(15),
        )

        # Grant Lambda permissions to start and monitor CodeBuild builds
        trigger_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                resources=[codebuild_project.project_arn],
            )
        )

        build_trigger = CustomResource(
            self,
            "BuildTrigger",
            service_token=trigger_fn.function_arn,
            properties={
                "ProjectName": codebuild_project.project_name,
                "SourceHash": source_asset.asset_hash,
            },
        )

        # --- 5. AgentCore Execution Role ---
        execution_role = create_agentcore_role(self, "AgentCoreExecutionRole")

        # --- 5b. AOSS Data Access Policy Updater ---
        # Automatically adds the execution role to the AOSS data access policy
        # so new environments can query OpenSearch Serverless without manual steps.
        if aoss_data_policy_name:
            aoss_policy_fn = lambda_.Function(
                self,
                "AossDataPolicyUpdater",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="aoss_policy_updater.handler",
                code=lambda_.Code.from_asset(infra_utils_dir),
                timeout=Duration.minutes(2),
            )

            aoss_policy_fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "aoss:GetAccessPolicy",
                        "aoss:UpdateAccessPolicy",
                    ],
                    resources=["*"],
                )
            )

            CustomResource(
                self,
                "AossDataPolicyTrigger",
                service_token=aoss_policy_fn.function_arn,
                properties={
                    "PolicyName": aoss_data_policy_name,
                    "RoleArn": execution_role.role_arn,
                },
            )

        # --- 6. CfnRuntime ---
        # Build network configuration
        network_config: dict = {"network_mode": network_mode}
        if network_mode == "PRIVATE" and subnets and security_groups:
            network_config["network_mode_config"] = {
                "subnets": subnets.split(","),
                "security_groups": security_groups.split(","),
            }

        runtime = bedrockagentcore.CfnRuntime(
            self,
            "AgentCoreRuntime",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=f"{ecr_repo.repository_uri}:latest",
                ),
            ),
            agent_runtime_name=f"agentcore_sales_agent_{env_name}",
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                **network_config,
            ),
            role_arn=execution_role.role_arn,
            protocol_configuration="HTTP",
            environment_variables={
                "PARAMETER_STORE_PREFIX": f"/agentcore/sales-agent/{env_name}/",
                "MEMORY_ID": memory_id,
            },
        )

        # CfnRuntime depends on build completing first
        runtime.node.add_dependency(build_trigger)

        # --- 7. SSM Parameters ---
        param_prefix = f"/agentcore/sales-agent/{env_name}"

        ssm.StringParameter(
            self,
            "ParamAossCollectionId",
            parameter_name=f"{param_prefix}/aoss_collection_id",
            string_value=aoss_endpoint or "NONE",
        )

        ssm.StringParameter(
            self,
            "ParamAossRegion",
            parameter_name=f"{param_prefix}/aoss_region",
            string_value=aoss_region,
        )

        ssm.StringParameter(
            self,
            "ParamItemTableName",
            parameter_name=f"{param_prefix}/item_table_name",
            string_value=item_table_name,
        )

        ssm.StringParameter(
            self,
            "ParamUserTableName",
            parameter_name=f"{param_prefix}/user_table_name",
            string_value=user_table_name,
        )

        ssm.StringParameter(
            self,
            "ParamRecommenderArn",
            parameter_name=f"{param_prefix}/recommender_arn",
            string_value=recommender_arn or "NONE",
        )

        ssm.StringParameter(
            self,
            "ParamModelId",
            parameter_name=f"{param_prefix}/model_id",
            string_value=model_id,
        )

        # --- 8. CfnOutputs ---
        CfnOutput(
            self,
            "RuntimeArn",
            value=runtime.attr_agent_runtime_arn,
            description="AgentCore Runtime ARN",
        )

        CfnOutput(
            self,
            "RuntimeId",
            value=runtime.attr_agent_runtime_id,
            description="AgentCore Runtime ID",
        )

        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=ecr_repo.repository_uri,
            description="ECR Repository URI",
        )

        CfnOutput(
            self,
            "ExecutionRoleArn",
            value=execution_role.role_arn,
            description="AgentCore Execution Role ARN",
        )
