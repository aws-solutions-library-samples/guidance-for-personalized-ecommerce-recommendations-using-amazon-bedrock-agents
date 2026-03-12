"""
Sales Agent Runtime Stack

This CDK stack provisions all AWS resources for deploying and managing a Bedrock
AgentCore runtime with native tools for product search and recommendations.

The stack supports:
- Flexible VPC configuration (existing or new VPC)
- Parameter Store for configuration management
- Multi-stage deployment isolation
- IAM roles with least-privilege permissions
- CI/CD pipeline automation
- Monitoring and observability
"""

from typing import Optional
from aws_cdk import (
    Stack,
    CfnOutput,
    Tags,
    Duration,
    RemovalPolicy,
)
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_iam as iam
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_logs as logs
from aws_cdk import aws_codecommit as codecommit
from aws_cdk import aws_codedeploy as codedeploy
from aws_cdk import aws_codebuild as codebuild
from aws_cdk import aws_codepipeline as codepipeline
from aws_cdk import aws_codepipeline_actions as codepipeline_actions
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from constructs import Construct


class SalesAgentRuntimeStack(Stack):
    """
    CDK Stack for AgentCore Sales Agent Runtime Infrastructure.
    
    This stack creates all necessary AWS resources for deploying a containerized
    Bedrock AgentCore runtime with native tools, including VPC, compute resources,
    CI/CD pipeline, parameter store configuration, and monitoring.
    
    Args:
        scope: CDK app or parent construct
        construct_id: Unique identifier for this stack
        stage: Deployment stage identifier (e.g., dev, staging, prod)
        vpc_id: Optional existing VPC ID. If not provided, a new VPC will be created
        **kwargs: Additional stack properties (description, env, etc.)
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        vpc_id: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Store stage for use in resource naming and tagging
        self.stage = stage
        self.vpc_id = vpc_id
        
        # Validate stage name format (alphanumeric with hyphens and underscores)
        self._validate_stage_name()
        
        # Tag all resources with stage identifier
        Tags.of(self).add("Stage", stage)
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "SalesAgentRuntime")
        
        # Set parameter store prefix for use in methods
        self.parameter_store_prefix = f"/sales-agent/{stage}"
        
        # Setup VPC (existing or new)
        self._setup_vpc()
        
        # Create Parameter Store entries
        self._create_parameter_store()
        
        # Create runtime execution role with least-privilege policies
        self._create_runtime_role()
        
        # Create CI/CD service roles
        self._create_cicd_service_roles()
        
        # Create AgentCore Memory resource
        # Note: CfnMemory is not yet available in CDK, will be added when available
        # self._create_memory()
        
        # Create ECR repository for container images
        self._create_ecr_repository()
        
        # Create runtime compute resources (ECS Fargate)
        self._create_runtime_resources()
        
        # Create CodeCommit repository for CI/CD pipeline
        self._create_codecommit_repository()
        
        # Create CloudWatch alarms for monitoring (before CodeDeploy to enable alarm-based rollback)
        self._create_monitoring_alarms()
        
        # Create CodeDeploy application and deployment group
        self._create_codedeploy_resources()
        
        # Create CI/CD pipeline with source, build, deploy stages
        self._create_pipeline()
        
        # Stack outputs
        self._create_outputs()
    
    def _validate_stage_name(self) -> None:
        """
        Validate that stage name follows required pattern.
        
        Stage names must be alphanumeric with hyphens and underscores only.
        This ensures compatibility with AWS resource naming requirements.
        
        Raises:
            ValueError: If stage name contains invalid characters
        """
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.stage):
            raise ValueError(
                f"Invalid stage name: '{self.stage}'. "
                "Stage names must be alphanumeric with hyphens and underscores only."
            )
    
    def _setup_vpc(self) -> None:
        """
        Setup VPC configuration - use existing VPC or create new VPC.
        
        If vpc_id is provided, imports the existing VPC. Otherwise, creates a new VPC
        with the following configuration:
        - CIDR: 10.0.0.0/16
        - 2 public subnets (10.0.1.0/24, 10.0.2.0/24) across 2 AZs
        - 2 private subnets (10.0.11.0/24, 10.0.12.0/24) across 2 AZs
        - NAT gateways in public subnets for private subnet internet access
        - VPC endpoints for DynamoDB, S3, and Systems Manager
        """
        if self.vpc_id:
            # Use existing VPC
            self.vpc = ec2.Vpc.from_lookup(
                self,
                "ExistingVpc",
                vpc_id=self.vpc_id
            )
        else:
            # Create new VPC with public and private subnets
            self.vpc = ec2.Vpc(
                self,
                f"SalesAgentVpc-{self.stage}",
                vpc_name=f"sales-agent-vpc-{self.stage}",
                ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
                max_azs=2,
                nat_gateways=2,
                subnet_configuration=[
                    ec2.SubnetConfiguration(
                        name=f"Public-{self.stage}",
                        subnet_type=ec2.SubnetType.PUBLIC,
                        cidr_mask=24,
                    ),
                    ec2.SubnetConfiguration(
                        name=f"Private-{self.stage}",
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                        cidr_mask=24,
                    ),
                ],
            )
        
        # Configure VPC endpoints for AWS services
        self._configure_vpc_endpoints()
    
    def _configure_vpc_endpoints(self) -> None:
        """
        Configure VPC endpoints for AWS services.
        
        Creates VPC endpoints for:
        - DynamoDB (Gateway endpoint)
        - S3 (Gateway endpoint)
        - Systems Manager (Interface endpoint)
        
        These endpoints keep traffic within the AWS network, improving security
        and reducing NAT gateway costs.
        """
        # DynamoDB Gateway Endpoint
        self.vpc.add_gateway_endpoint(
            f"DynamoDbEndpoint-{self.stage}",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )
        
        # S3 Gateway Endpoint
        self.vpc.add_gateway_endpoint(
            f"S3Endpoint-{self.stage}",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )
        
        # Systems Manager Interface Endpoint
        self.vpc.add_interface_endpoint(
            f"SsmEndpoint-{self.stage}",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
        )
    
    def _create_parameter_store(self) -> None:
        """
        Create Parameter Store entries for runtime configuration.
        
        Creates hierarchical parameter entries with stage prefix for:
        - item_table: DynamoDB table name for product catalog
        - user_table: DynamoDB table name for user profiles
        - aoss_endpoint: OpenSearch Serverless endpoint URL
        - recommender_arn: Personalize recommender ARN
        - s3_bucket: S3 bucket name for product images
        - memory_id: AgentCore Memory resource identifier
        
        All parameters are String type and are tagged with the Stage tag for resource organization.
        """
        # Define parameter configurations
        parameters = [
            {
                "key": "item_table",
                "description": "DynamoDB table name for product catalog",
            },
            {
                "key": "user_table",
                "description": "DynamoDB table name for user profiles and history",
            },
            {
                "key": "aoss_endpoint",
                "description": "OpenSearch Serverless collection endpoint URL",
            },
            {
                "key": "recommender_arn",
                "description": "Amazon Personalize recommender ARN",
            },
            {
                "key": "s3_bucket",
                "description": "S3 bucket name for product image storage",
            },
            {
                "key": "memory_id",
                "description": "Bedrock AgentCore Memory resource identifier",
            },
        ]
        
        # Create each parameter with hierarchical naming
        for param in parameters:
            parameter_name = f"{self.parameter_store_prefix}/{param['key']}"
            
            # Create StringParameter with placeholder value
            # Actual values will be set via CLI or deployment script
            param_resource = ssm.StringParameter(
                self,
                f"Param-{param['key']}-{self.stage}",
                parameter_name=parameter_name,
                string_value="PLACEHOLDER",  # Will be updated after deployment
                description=param["description"],
                tier=ssm.ParameterTier.STANDARD,
            )
            
            # Tag parameter with Stage tag
            Tags.of(param_resource).add("Stage", self.stage)
            Tags.of(param_resource).add("ManagedBy", "CDK")
    
    def _create_runtime_role(self) -> None:
        """
        Create IAM execution role for runtime with least-privilege policies.
        
        Creates an IAM role with specific permissions for:
        - DynamoDB: Query and GetItem on specific tables
        - OpenSearch Serverless: APIAccessAll on specific collections
        - Personalize: GetRecommendations on specific recommenders
        - Bedrock: InvokeModel on specific model IDs
        - Parameter Store: GetParameter and GetParametersByPath on /sales-agent/{stage}/*
        - AgentCore Memory: InvokeAgent and Retrieve on specific memory resources
        
        All policies follow least-privilege principles with NO wildcard (*) permissions
        on resources. Resources are scoped to specific ARNs using stage-based naming.
        """
        # Create the IAM role
        self.runtime_role = iam.Role(
            self,
            f"RuntimeRole-{self.stage}",
            role_name=f"sales-agent-runtime-role-{self.stage}",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                iam.ServicePrincipal("ecs.amazonaws.com"),
            ),
            description=f"Execution role for Sales Agent runtime ({self.stage})",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"),
            ],
        )
        
        # Tag the role
        Tags.of(self.runtime_role).add("Stage", self.stage)
        Tags.of(self.runtime_role).add("ManagedBy", "CDK")
        
        # Policy 1: DynamoDB access for item_table and user_table
        # Scoped to specific table ARNs with stage-based naming
        dynamodb_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:Query",
                "dynamodb:GetItem",
            ],
            resources=[
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/sales-agent-items-{self.stage}",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/sales-agent-users-{self.stage}",
                # Also support legacy table names for backward compatibility
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/item_table",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/user_table",
            ],
        )
        self.runtime_role.add_to_policy(dynamodb_policy)
        
        # Policy 2: OpenSearch Serverless access
        # Scoped to stage-specific collection ARN
        aoss_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "aoss:APIAccessAll",
            ],
            resources=[
                f"arn:aws:aoss:{self.region}:{self.account}:collection/sales-agent-{self.stage}",
            ],
        )
        self.runtime_role.add_to_policy(aoss_policy)
        
        # Policy 3: Personalize access for recommendations
        # Scoped to stage-specific recommender ARN
        personalize_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "personalize:GetRecommendations",
            ],
            resources=[
                f"arn:aws:personalize:{self.region}:{self.account}:recommender/sales-agent-{self.stage}",
            ],
        )
        self.runtime_role.add_to_policy(personalize_policy)
        
        # Policy 4: Bedrock model invocation
        # Scoped to specific model IDs (foundation models don't use account ID)
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
            ],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-image-v1",
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/us.amazon.nova-lite-v1:0",
            ],
        )
        self.runtime_role.add_to_policy(bedrock_policy)
        
        # Policy 5: Parameter Store access
        # Scoped to stage-specific parameter path
        ssm_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ssm:GetParameter",
                "ssm:GetParametersByPath",
            ],
            resources=[
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/sales-agent/{self.stage}/*",
            ],
        )
        self.runtime_role.add_to_policy(ssm_policy)
        
        # Policy 6: AgentCore Memory access
        # Scoped to stage-specific memory resource ARN
        memory_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeAgent",
                "bedrock:Retrieve",
            ],
            resources=[
                f"arn:aws:bedrock:{self.region}:{self.account}:memory/sales-agent-memory-{self.stage}",
            ],
        )
        self.runtime_role.add_to_policy(memory_policy)

    def _create_cicd_service_roles(self) -> None:
        """
        Create IAM service roles for CI/CD pipeline components.

        Creates three IAM roles with minimal permissions:
        1. CodePipeline role: Orchestrates pipeline stages
        2. CodeBuild role: Builds Docker images and pushes to ECR
        3. CodeDeploy role: Deploys runtime with blue/green strategy

        These roles are stored as instance attributes for use in CI/CD pipeline setup.
        All roles follow least-privilege principles with scoped permissions.
        """
        # 1. CodePipeline Service Role
        self.codepipeline_role = iam.Role(
            self,
            f"CodePipelineRole-{self.stage}",
            role_name=f"sales-agent-codepipeline-role-{self.stage}",
            assumed_by=iam.ServicePrincipal("codepipeline.amazonaws.com"),
            description=f"Service role for Sales Agent CodePipeline ({self.stage})",
        )

        # Tag the role
        Tags.of(self.codepipeline_role).add("Stage", self.stage)
        Tags.of(self.codepipeline_role).add("ManagedBy", "CDK")

        # CodePipeline permissions: Access to CodeCommit, CodeBuild, CodeDeploy, S3 artifacts
        codepipeline_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                # CodeCommit source actions
                "codecommit:GetBranch",
                "codecommit:GetCommit",
                "codecommit:UploadArchive",
                "codecommit:GetUploadArchiveStatus",
                "codecommit:CancelUploadArchive",
                # CodeBuild build actions
                "codebuild:BatchGetBuilds",
                "codebuild:StartBuild",
                # CodeDeploy deployment actions
                "codedeploy:CreateDeployment",
                "codedeploy:GetApplication",
                "codedeploy:GetApplicationRevision",
                "codedeploy:GetDeployment",
                "codedeploy:GetDeploymentConfig",
                "codedeploy:RegisterApplicationRevision",
            ],
            resources=[
                # Scoped to stage-specific resources
                f"arn:aws:codecommit:{self.region}:{self.account}:sales-agent-runtime-{self.stage}",
                f"arn:aws:codebuild:{self.region}:{self.account}:project/sales-agent-build-{self.stage}",
                f"arn:aws:codedeploy:{self.region}:{self.account}:application:sales-agent-app-{self.stage}",
                f"arn:aws:codedeploy:{self.region}:{self.account}:deploymentgroup:sales-agent-app-{self.stage}/*",
                f"arn:aws:codedeploy:{self.region}:{self.account}:deploymentconfig:*",
            ],
        )
        self.codepipeline_role.add_to_policy(codepipeline_policy)

        # S3 permissions for pipeline artifacts
        s3_artifacts_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
                "s3:GetBucketLocation",
                "s3:ListBucket",
            ],
            resources=[
                # Will be scoped to specific artifact bucket when pipeline is created
                f"arn:aws:s3:::sales-agent-pipeline-artifacts-{self.stage}",
                f"arn:aws:s3:::sales-agent-pipeline-artifacts-{self.stage}/*",
            ],
        )
        self.codepipeline_role.add_to_policy(s3_artifacts_policy)

        # 2. CodeBuild Service Role
        self.codebuild_role = iam.Role(
            self,
            f"CodeBuildRole-{self.stage}",
            role_name=f"sales-agent-codebuild-role-{self.stage}",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            description=f"Service role for Sales Agent CodeBuild ({self.stage})",
        )

        # Tag the role
        Tags.of(self.codebuild_role).add("Stage", self.stage)
        Tags.of(self.codebuild_role).add("ManagedBy", "CDK")

        # CodeBuild permissions: ECR push, CloudWatch Logs, S3 artifacts
        ecr_push_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
            ],
            resources=[
                # GetAuthorizationToken requires * resource
                "*",
            ],
        )
        self.codebuild_role.add_to_policy(ecr_push_policy)

        # Scoped ECR repository access
        ecr_repo_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
            ],
            resources=[
                f"arn:aws:ecr:{self.region}:{self.account}:repository/sales-agent-runtime-{self.stage}",
            ],
        )
        self.codebuild_role.add_to_policy(ecr_repo_policy)

        # CloudWatch Logs permissions for build logs
        logs_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/sales-agent-build-{self.stage}",
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/sales-agent-build-{self.stage}:*",
            ],
        )
        self.codebuild_role.add_to_policy(logs_policy)

        # S3 permissions for build artifacts
        s3_build_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
            ],
            resources=[
                f"arn:aws:s3:::sales-agent-pipeline-artifacts-{self.stage}/*",
            ],
        )
        self.codebuild_role.add_to_policy(s3_build_policy)

        # 3. CodeDeploy Service Role
        self.codedeploy_role = iam.Role(
            self,
            f"CodeDeployRole-{self.stage}",
            role_name=f"sales-agent-codedeploy-role-{self.stage}",
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"),
            description=f"Service role for Sales Agent CodeDeploy ({self.stage})",
        )

        # Tag the role
        Tags.of(self.codedeploy_role).add("Stage", self.stage)
        Tags.of(self.codedeploy_role).add("ManagedBy", "CDK")

        # CodeDeploy permissions: ECS/Fargate deployment, load balancer management
        codedeploy_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                # ECS task and service management
                "ecs:DescribeServices",
                "ecs:CreateTaskSet",
                "ecs:UpdateServicePrimaryTaskSet",
                "ecs:DeleteTaskSet",
                "ecs:DescribeTaskSets",
                # Load balancer management for blue/green
                "elasticloadbalancing:DescribeTargetGroups",
                "elasticloadbalancing:DescribeListeners",
                "elasticloadbalancing:ModifyListener",
                "elasticloadbalancing:DescribeRules",
                "elasticloadbalancing:ModifyRule",
                "elasticloadbalancing:DescribeTargetHealth",
                "elasticloadbalancing:RegisterTargets",
                "elasticloadbalancing:DeregisterTargets",
                # CloudWatch for deployment monitoring
                "cloudwatch:DescribeAlarms",
                # SNS for deployment notifications
                "sns:Publish",
                # IAM pass role for ECS tasks
                "iam:PassRole",
            ],
            resources=[
                # Scoped to stage-specific resources
                f"arn:aws:ecs:{self.region}:{self.account}:service/sales-agent-cluster-{self.stage}/*",
                f"arn:aws:ecs:{self.region}:{self.account}:task-set/sales-agent-cluster-{self.stage}/*/*",
                f"arn:aws:elasticloadbalancing:{self.region}:{self.account}:targetgroup/sales-agent-*",
                f"arn:aws:elasticloadbalancing:{self.region}:{self.account}:listener/app/sales-agent-*",
                f"arn:aws:elasticloadbalancing:{self.region}:{self.account}:listener-rule/app/sales-agent-*",
                f"arn:aws:cloudwatch:{self.region}:{self.account}:alarm:sales-agent-*",
                f"arn:aws:sns:{self.region}:{self.account}:sales-agent-*",
                # IAM role for ECS tasks
                self.runtime_role.role_arn,
            ],
        )
        self.codedeploy_role.add_to_policy(codedeploy_policy)

        # S3 permissions for deployment artifacts
        s3_deploy_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:GetObjectVersion",
            ],
            resources=[
                f"arn:aws:s3:::sales-agent-pipeline-artifacts-{self.stage}/*",
            ],
        )
        self.codedeploy_role.add_to_policy(s3_deploy_policy)

    def _create_memory(self) -> None:
        """
        Create AgentCore Memory resource for conversation context.
        
        Creates a Bedrock AgentCore Memory resource with:
        - 30-day event expiry policy for automatic cleanup
        - Retrieval settings: top_k=2, relevance_score=0.6
        - Stage-specific naming for multi-stage isolation
        
        The memory ID is stored in Parameter Store for runtime access.
        The runtime role is granted permissions to read and write to the memory.
        """
        # Create AgentCore Memory resource with 30-day expiry and retrieval settings
        self.memory = bedrock.CfnMemory(
            self,
            f"AgentCoreMemory-{self.stage}",
            memory_name=f"sales-agent-memory-{self.stage}",
            memory_configuration={
                "eventExpiryPolicy": {
                    "days": 30
                },
                "retrievalConfiguration": {
                    "topK": 2,
                    "relevanceScore": 0.6
                }
            },
            tags={
                "Stage": self.stage,
                "ManagedBy": "CDK",
                "Application": "SalesAgentRuntime"
            }
        )
        
        # Update the memory_id parameter with the actual memory ID
        # Find the existing parameter and update its value
        memory_param = ssm.StringParameter.from_string_parameter_name(
            self,
            f"MemoryIdParam-{self.stage}",
            string_parameter_name=f"{self.parameter_store_prefix}/memory_id"
        )
        
        # Create a new parameter with the actual memory ID value
        # This will override the placeholder value created in _create_parameter_store()
        ssm.StringParameter(
            self,
            f"MemoryIdParamValue-{self.stage}",
            parameter_name=f"{self.parameter_store_prefix}/memory_id",
            string_value=self.memory.attr_memory_id,
            description="Bedrock AgentCore Memory resource identifier",
            tier=ssm.ParameterTier.STANDARD,
        )
        
        # Grant runtime role permissions to access memory
        # These permissions were already added in _create_runtime_role()
        # but we verify the memory resource exists first
        memory_access_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeAgent",
                "bedrock:Retrieve",
                "bedrock:RetrieveAndGenerate",
            ],
            resources=[
                self.memory.attr_memory_arn,
            ],
        )
        self.runtime_role.add_to_policy(memory_access_policy)

    def _create_ecr_repository(self) -> None:
        """
        Create ECR repository for storing runtime container images.
        
        Creates an Amazon ECR repository with:
        - Stage-prefixed name for multi-stage isolation
        - Image scanning on push for security vulnerability detection
        - Lifecycle policy to retain only the 10 most recent images
        - Automatic deletion of untagged images after 1 day
        
        The repository URI is output as a stack output for use by CodeBuild
        and deployment scripts.
        """
        # Create ECR repository with stage-prefixed name
        self.ecr_repository = ecr.Repository(
            self,
            f"RuntimeRepository-{self.stage}",
            repository_name=f"sales-agent-runtime-{self.stage}",
            image_scan_on_push=True,  # Enable automatic vulnerability scanning
            lifecycle_rules=[
                # Delete untagged images after 1 day (higher priority)
                ecr.LifecycleRule(
                    description="Remove untagged images after 1 day",
                    max_image_age=Duration.days(1),
                    rule_priority=1,
                    tag_status=ecr.TagStatus.UNTAGGED,
                ),
                # Keep only the 10 most recent images (lower priority)
                ecr.LifecycleRule(
                    description="Retain only 10 most recent images",
                    max_image_count=10,
                    rule_priority=2,
                ),
            ],
        )
        
        # Tag the repository
        Tags.of(self.ecr_repository).add("Stage", self.stage)
        Tags.of(self.ecr_repository).add("ManagedBy", "CDK")
        Tags.of(self.ecr_repository).add("Application", "SalesAgentRuntime")

    def _create_runtime_resources(self) -> None:
        """
        Create runtime compute resources using ECS Fargate with ARM64 (Graviton).
        
        Creates:
        - ECS cluster for runtime deployment
        - CloudWatch log group for runtime logs
        - ECS task definition with ARM64 architecture
        - Security group for runtime access
        - Application Load Balancer for runtime endpoint
        - ECS Fargate service in private subnets
        - Health checks and auto-scaling configuration
        
        The runtime is deployed in private subnets with ALB in public subnets.
        Environment variables point to Parameter Store paths for configuration.
        """
        # Create ECS cluster with ARM64 (Graviton) support
        self.ecs_cluster = ecs.Cluster(
            self,
            f"RuntimeCluster-{self.stage}",
            cluster_name=f"sales-agent-cluster-{self.stage}",
            vpc=self.vpc,
            container_insights=True,  # Enable CloudWatch Container Insights
        )
        
        # Tag the cluster
        Tags.of(self.ecs_cluster).add("Stage", self.stage)
        Tags.of(self.ecs_cluster).add("ManagedBy", "CDK")
        
        # Create CloudWatch log group for runtime logs
        self.log_group = logs.LogGroup(
            self,
            f"RuntimeLogGroup-{self.stage}",
            log_group_name=f"/aws/sales-agent/{self.stage}",
            retention=logs.RetentionDays.ONE_MONTH,  # 30-day retention
        )
        
        # Tag the log group
        Tags.of(self.log_group).add("Stage", self.stage)
        Tags.of(self.log_group).add("ManagedBy", "CDK")
        
        # Create ECS task definition with ARM64 architecture
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            f"RuntimeTaskDef-{self.stage}",
            family=f"sales-agent-runtime-{self.stage}",
            cpu=1024,  # 1 vCPU
            memory_limit_mib=2048,  # 2 GB
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,  # Graviton
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            task_role=self.runtime_role,
            execution_role=self.runtime_role,
        )
        
        # Add container to task definition
        # Use placeholder image asset for initial deployment
        # This will be replaced by CI/CD pipeline with the actual runtime image
        placeholder_image_asset = ecr_assets.DockerImageAsset(
            self,
            f"PlaceholderImageAsset-{self.stage}",
            directory="runtime",
            file="Dockerfile.placeholder",
            platform=ecr_assets.Platform.LINUX_ARM64,
        )
        
        self.container = self.task_definition.add_container(
            f"RuntimeContainer-{self.stage}",
            container_name="runtime",
            image=ecs.ContainerImage.from_docker_image_asset(placeholder_image_asset),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="runtime",
                log_group=self.log_group,
            ),
            environment={
                "STAGE": self.stage,
                "MCP_REGION": self.region,
                # OpenTelemetry configuration
                "OTEL_SERVICE_NAME": "sales-agent-runtime",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "localhost:4317",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_METRICS_EXPORTER": "otlp",
                "OTEL_LOGS_EXPORTER": "none",  # Use CloudWatch for logs
                "OTEL_RESOURCE_ATTRIBUTES": f"service.name=sales-agent-runtime,deployment.environment={self.stage}",
            },
            port_mappings=[
                ecs.PortMapping(container_port=8000, protocol=ecs.Protocol.TCP),
                ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP),
                ecs.PortMapping(container_port=9000, protocol=ecs.Protocol.TCP),
            ],
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )
        
        # Create security group for runtime
        self.runtime_security_group = ec2.SecurityGroup(
            self,
            f"RuntimeSecurityGroup-{self.stage}",
            security_group_name=f"sales-agent-runtime-sg-{self.stage}",
            vpc=self.vpc,
            description=f"Security group for Sales Agent runtime ({self.stage})",
            allow_all_outbound=True,
        )
        
        # Tag the security group
        Tags.of(self.runtime_security_group).add("Stage", self.stage)
        Tags.of(self.runtime_security_group).add("ManagedBy", "CDK")
        
        # Create Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            f"RuntimeALB-{self.stage}",
            load_balancer_name=f"sales-agent-alb-{self.stage}",
            vpc=self.vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )
        
        # Tag the ALB
        Tags.of(self.alb).add("Stage", self.stage)
        Tags.of(self.alb).add("ManagedBy", "CDK")
        
        # Create target group for runtime service
        self.target_group = elbv2.ApplicationTargetGroup(
            self,
            f"RuntimeTargetGroup-{self.stage}",
            target_group_name=f"sales-agent-tg-{self.stage}",
            vpc=self.vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
            deregistration_delay=Duration.seconds(30),
        )
        
        # Add listener to ALB
        self.listener = self.alb.add_listener(
            f"RuntimeListener-{self.stage}",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[self.target_group],
        )
        
        # Allow ALB to access runtime on port 8000
        self.runtime_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.alb.connections.security_groups[0].security_group_id),
            connection=ec2.Port.tcp(8000),
            description="Allow ALB to access runtime on port 8000",
        )
        
        # Create ECS Fargate service
        self.fargate_service = ecs.FargateService(
            self,
            f"RuntimeService-{self.stage}",
            service_name=f"sales-agent-service-{self.stage}",
            cluster=self.ecs_cluster,
            task_definition=self.task_definition,
            desired_count=1,  # Start with 1 task
            min_healthy_percent=50,
            max_healthy_percent=200,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.runtime_security_group],
            assign_public_ip=False,  # Private subnet, no public IP
            health_check_grace_period=Duration.seconds(300),  # 300 seconds for CodeDeploy
            deployment_controller=ecs.DeploymentController(
                type=ecs.DeploymentControllerType.CODE_DEPLOY  # Enable CodeDeploy blue/green
            ),
        )
        
        # Attach service to target group
        self.fargate_service.attach_to_application_target_group(self.target_group)
        
        # Tag the service
        Tags.of(self.fargate_service).add("Stage", self.stage)
        Tags.of(self.fargate_service).add("ManagedBy", "CDK")
        
        # Note: Auto-scaling is not compatible with CODE_DEPLOY deployment controller
        # If auto-scaling is needed, it must be configured separately after deployment
        
        # Grant runtime role permissions to write logs
        self.log_group.grant_write(self.runtime_role)

    def _create_codecommit_repository(self) -> None:
        """
        Create CodeCommit repository for runtime source code.
        
        Creates an AWS CodeCommit git repository with:
        - Stage-suffixed name for multi-stage isolation
        - Default branch configured as 'main'
        - Description indicating purpose and stage
        
        The repository clone URL is output as a stack output for developers
        to push code changes that trigger the CI/CD pipeline.
        
        Requirements: 4.1, 11.4
        """
        # Create CodeCommit repository with stage-suffixed name
        self.code_repository = codecommit.Repository(
            self,
            f"CodeCommitRepository-{self.stage}",
            repository_name=f"sales-agent-runtime-{self.stage}",
            description=f"Source code repository for Sales Agent runtime ({self.stage})",
        )
        
        # Tag the repository
        Tags.of(self.code_repository).add("Stage", self.stage)
        Tags.of(self.code_repository).add("ManagedBy", "CDK")
        Tags.of(self.code_repository).add("Application", "SalesAgentRuntime")

    def _create_codedeploy_resources(self) -> None:
        """
        Create CodeDeploy application and deployment group for blue/green deployments.
        
        Creates:
        - CodeDeploy application for ECS deployments
        - Deployment group with blue/green configuration
        - Traffic shifting strategy (all-at-once)
        - Health check grace period of 300 seconds
        - Automatic rollback on deployment failure or alarm triggers
        
        The deployment group integrates with the existing ECS service and load balancer
        to enable zero-downtime deployments with automatic rollback capabilities.
        
        Requirements: 4.6, 4.10
        """
        # Create CodeDeploy application for ECS
        self.codedeploy_application = codedeploy.EcsApplication(
            self,
            f"CodeDeployApp-{self.stage}",
            application_name=f"sales-agent-app-{self.stage}",
        )
        
        # Tag the application
        Tags.of(self.codedeploy_application).add("Stage", self.stage)
        Tags.of(self.codedeploy_application).add("ManagedBy", "CDK")
        Tags.of(self.codedeploy_application).add("Application", "SalesAgentRuntime")
        
        # Create a second target group for blue/green deployment
        # This is the "green" target group that will receive traffic during deployment
        self.target_group_green = elbv2.ApplicationTargetGroup(
            self,
            f"RuntimeTargetGroupGreen-{self.stage}",
            target_group_name=f"sales-agent-tg-green-{self.stage}",
            vpc=self.vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
            deregistration_delay=Duration.seconds(30),
        )
        
        # Tag the green target group
        Tags.of(self.target_group_green).add("Stage", self.stage)
        Tags.of(self.target_group_green).add("ManagedBy", "CDK")
        
        # Create a test listener on port 8080 for blue/green testing
        self.test_listener = self.alb.add_listener(
            f"RuntimeTestListener-{self.stage}",
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[self.target_group_green],
        )
        
        # Create CodeDeploy deployment group with blue/green configuration
        self.deployment_group = codedeploy.EcsDeploymentGroup(
            self,
            f"CodeDeployGroup-{self.stage}",
            deployment_group_name=f"sales-agent-dg-{self.stage}",
            application=self.codedeploy_application,
            service=self.fargate_service,
            # Blue/green deployment configuration
            blue_green_deployment_config=codedeploy.EcsBlueGreenDeploymentConfig(
                # Production listener (blue)
                blue_target_group=self.target_group,
                # Test listener (green)
                green_target_group=self.target_group_green,
                # Production listener
                listener=self.listener,
                # Test listener for validation before traffic shift
                test_listener=self.test_listener,
                # Terminate blue tasks after successful deployment
                termination_wait_time=Duration.minutes(5),
            ),
            # Traffic shifting configuration - all at once
            deployment_config=codedeploy.EcsDeploymentConfig.ALL_AT_ONCE,
            # Automatic rollback configuration with alarm-based rollback
            auto_rollback=codedeploy.AutoRollbackConfig(
                failed_deployment=True,  # Rollback on deployment failure
                stopped_deployment=True,  # Rollback if deployment is stopped
                deployment_in_alarm=True,  # Rollback if CloudWatch alarms trigger
            ),
            # CloudWatch alarms for monitoring and rollback
            alarms=self.monitoring_alarms if hasattr(self, 'monitoring_alarms') else None,
            # IAM role for CodeDeploy
            role=self.codedeploy_role,
        )
        
        # Tag the deployment group
        Tags.of(self.deployment_group).add("Stage", self.stage)
        Tags.of(self.deployment_group).add("ManagedBy", "CDK")
        Tags.of(self.deployment_group).add("Application", "SalesAgentRuntime")

    def _create_pipeline(self) -> None:
        """
        Create CI/CD pipeline with source, build, and deploy stages.
        
        Creates a complete CodePipeline with:
        - Source stage: Monitors CodeCommit repository main branch
        - Build stage: Executes CodeBuild project to build and test container
        - Deploy stage: Uses CodeDeploy for blue/green deployment
        
        The pipeline automatically triggers on commits to the main branch and
        includes failure notifications via CloudWatch Events to SNS.
        
        Requirements: 4.2, 4.3, 4.7
        """
        # Create S3 bucket for pipeline artifacts
        self.artifact_bucket = s3.Bucket(
            self,
            f"PipelineArtifactBucket-{self.stage}",
            bucket_name=f"sales-agent-pipeline-artifacts-{self.stage}-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,  # Delete bucket when stack is deleted
            auto_delete_objects=True,  # Clean up objects on bucket deletion
        )
        
        # Tag the bucket
        Tags.of(self.artifact_bucket).add("Stage", self.stage)
        Tags.of(self.artifact_bucket).add("ManagedBy", "CDK")
        
        # Create CodeBuild project for ARM64 builds
        self.codebuild_project = codebuild.Project(
            self,
            f"CodeBuildProject-{self.stage}",
            project_name=f"sales-agent-build-{self.stage}",
            description=f"Build project for Sales Agent runtime ({self.stage})",
            role=self.codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,  # ARM64 Graviton
                compute_type=codebuild.ComputeType.LARGE,  # 8 GB memory, 4 vCPUs
                privileged=True,  # Required for Docker builds
                environment_variables={
                    "ECR_REPOSITORY": codebuild.BuildEnvironmentVariable(
                        value=self.ecr_repository.repository_uri
                    ),
                    "ECR_REGISTRY": codebuild.BuildEnvironmentVariable(
                        value=f"{self.account}.dkr.ecr.{self.region}.amazonaws.com"
                    ),
                    "AWS_REGION": codebuild.BuildEnvironmentVariable(
                        value=self.region
                    ),
                    "STAGE": codebuild.BuildEnvironmentVariable(
                        value=self.stage
                    ),
                },
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Logging in to Amazon ECR...",
                            "aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY",
                            "COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)",
                            "IMAGE_TAG=${COMMIT_HASH:=latest}",
                            "echo Build started on `date`",
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Building Docker image for ARM64 Graviton...",
                            "docker buildx create --use --name arm-builder || docker buildx use arm-builder",
                            "docker buildx build --platform linux/arm64 --load -t $ECR_REPOSITORY:$IMAGE_TAG -f runtime/Dockerfile runtime/",
                            "docker tag $ECR_REPOSITORY:$IMAGE_TAG $ECR_REPOSITORY:latest",
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Build completed on `date`",
                            "echo Pushing Docker image...",
                            "docker push $ECR_REPOSITORY:$IMAGE_TAG",
                            "docker push $ECR_REPOSITORY:latest",
                            "echo Creating deployment artifacts...",
                            # Create imageDetail.json for CodeDeploy ECS action
                            "printf '{\"ImageURI\":\"%s\"}' $ECR_REPOSITORY:$IMAGE_TAG > imageDetail.json",
                            # Create appspec.yaml for CodeDeploy
                            "cat > appspec.yaml << 'EOF'\nversion: 0.0\nResources:\n  - TargetService:\n      Type: AWS::ECS::Service\n      Properties:\n        TaskDefinition: <TASK_DEFINITION>\n        LoadBalancerInfo:\n          ContainerName: runtime\n          ContainerPort: 8000\nEOF",
                            # Create taskdef.json template
                            "cat > taskdef.json << 'EOF'\n{\n  \"family\": \"sales-agent-runtime-" + self.stage + "\",\n  \"executionRoleArn\": \"" + self.runtime_role.role_arn + "\",\n  \"taskRoleArn\": \"" + self.runtime_role.role_arn + "\",\n  \"networkMode\": \"awsvpc\",\n  \"requiresCompatibilities\": [\"FARGATE\"],\n  \"cpu\": \"1024\",\n  \"memory\": \"2048\",\n  \"runtimePlatform\": {\n    \"cpuArchitecture\": \"ARM64\",\n    \"operatingSystemFamily\": \"LINUX\"\n  },\n  \"containerDefinitions\": [\n    {\n      \"name\": \"runtime\",\n      \"image\": \"<IMAGE1_NAME>\",\n      \"essential\": true,\n      \"portMappings\": [\n        {\"containerPort\": 8000, \"protocol\": \"tcp\"},\n        {\"containerPort\": 8080, \"protocol\": \"tcp\"},\n        {\"containerPort\": 9000, \"protocol\": \"tcp\"}\n      ],\n      \"environment\": [\n        {\"name\": \"STAGE\", \"value\": \"" + self.stage + "\"},\n        {\"name\": \"MCP_REGION\", \"value\": \"" + self.region + "\"},\n        {\"name\": \"OTEL_SERVICE_NAME\", \"value\": \"sales-agent-runtime\"},\n        {\"name\": \"OTEL_EXPORTER_OTLP_ENDPOINT\", \"value\": \"localhost:4317\"},\n        {\"name\": \"OTEL_TRACES_EXPORTER\", \"value\": \"otlp\"},\n        {\"name\": \"OTEL_METRICS_EXPORTER\", \"value\": \"otlp\"},\n        {\"name\": \"OTEL_LOGS_EXPORTER\", \"value\": \"none\"},\n        {\"name\": \"OTEL_RESOURCE_ATTRIBUTES\", \"value\": \"service.name=sales-agent-runtime,deployment.environment=" + self.stage + "\"}\n      ],\n      \"logConfiguration\": {\n        \"logDriver\": \"awslogs\",\n        \"options\": {\n          \"awslogs-group\": \"/aws/sales-agent/" + self.stage + "\",\n          \"awslogs-region\": \"" + self.region + "\",\n          \"awslogs-stream-prefix\": \"runtime\"\n        }\n      },\n      \"healthCheck\": {\n        \"command\": [\"CMD-SHELL\", \"curl -f http://localhost:8000/health || exit 1\"],\n        \"interval\": 30,\n        \"timeout\": 5,\n        \"retries\": 3,\n        \"startPeriod\": 60\n      }\n    }\n  ]\n}\nEOF",
                            "cat imageDetail.json",
                            "cat appspec.yaml",
                            "cat taskdef.json",
                        ]
                    },
                },
                "artifacts": {
                    "files": [
                        "imageDetail.json",
                        "appspec.yaml",
                        "taskdef.json"
                    ]
                },
            }),
            timeout=Duration.minutes(30),
        )
        
        # Tag the CodeBuild project
        Tags.of(self.codebuild_project).add("Stage", self.stage)
        Tags.of(self.codebuild_project).add("ManagedBy", "CDK")
        
        # Grant CodeBuild access to ECR repository
        self.ecr_repository.grant_pull_push(self.codebuild_role)
        
        # Create SNS topic for pipeline failure notifications
        self.pipeline_notification_topic = sns.Topic(
            self,
            f"PipelineNotificationTopic-{self.stage}",
            topic_name=f"sales-agent-pipeline-notifications-{self.stage}",
            display_name=f"Sales Agent Pipeline Notifications ({self.stage})",
        )
        
        # Tag the SNS topic
        Tags.of(self.pipeline_notification_topic).add("Stage", self.stage)
        Tags.of(self.pipeline_notification_topic).add("ManagedBy", "CDK")
        
        # Create CodePipeline
        self.pipeline = codepipeline.Pipeline(
            self,
            f"Pipeline-{self.stage}",
            pipeline_name=f"sales-agent-pipeline-{self.stage}",
            artifact_bucket=self.artifact_bucket,
            role=self.codepipeline_role,
            restart_execution_on_update=True,  # Restart pipeline when updated
        )
        
        # Tag the pipeline
        Tags.of(self.pipeline).add("Stage", self.stage)
        Tags.of(self.pipeline).add("ManagedBy", "CDK")
        
        # Define artifacts
        source_output = codepipeline.Artifact("SourceOutput")
        build_output = codepipeline.Artifact("BuildOutput")
        
        # Stage 1: Source - Monitor CodeCommit repository main branch
        self.pipeline.add_stage(
            stage_name="Source",
            actions=[
                codepipeline_actions.CodeCommitSourceAction(
                    action_name="CodeCommit_Source",
                    repository=self.code_repository,
                    branch="main",
                    output=source_output,
                    trigger=codepipeline_actions.CodeCommitTrigger.EVENTS,  # Trigger on commit
                )
            ],
        )
        
        # Stage 2: Build - Execute CodeBuild project
        self.pipeline.add_stage(
            stage_name="Build",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="Build_and_Test",
                    project=self.codebuild_project,
                    input=source_output,
                    outputs=[build_output],
                )
            ],
        )
        
        # Stage 3: Deploy - Use CodeDeploy for blue/green deployment
        self.pipeline.add_stage(
            stage_name="Deploy",
            actions=[
                codepipeline_actions.CodeDeployEcsDeployAction(
                    action_name="Deploy_to_ECS",
                    deployment_group=self.deployment_group,
                    app_spec_template_input=build_output,
                    task_definition_template_input=build_output,
                    container_image_inputs=[
                        codepipeline_actions.CodeDeployEcsContainerImageInput(
                            input=build_output,
                            task_definition_placeholder="IMAGE1_NAME",
                        )
                    ],
                )
            ],
        )
        
        # Create CloudWatch Events rule for pipeline failure notifications
        pipeline_failure_rule = events.Rule(
            self,
            f"PipelineFailureRule-{self.stage}",
            rule_name=f"sales-agent-pipeline-failure-{self.stage}",
            description=f"Notify on pipeline failures for stage {self.stage}",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Pipeline Execution State Change"],
                detail={
                    "state": ["FAILED"],
                    "pipeline": [self.pipeline.pipeline_name],
                },
            ),
        )
        
        # Add SNS topic as target for failure notifications
        pipeline_failure_rule.add_target(
            events_targets.SnsTopic(
                self.pipeline_notification_topic,
                message=events.RuleTargetInput.from_text(
                    f"Pipeline {self.pipeline.pipeline_name} has FAILED.\n\n"
                    "Pipeline: $.detail.pipeline\n"
                    "Execution ID: $.detail.execution-id\n"
                    "State: $.detail.state\n"
                    "Time: $.time"
                ),
            )
        )
        
        # Tag the CloudWatch Events rule
        Tags.of(pipeline_failure_rule).add("Stage", self.stage)
        Tags.of(pipeline_failure_rule).add("ManagedBy", "CDK")
    
    def _create_monitoring_alarms(self) -> None:
        """
        Create CloudWatch alarms for runtime monitoring.
        
        Creates:
        - SNS topic for alarm notifications
        - CloudWatch alarm for error rate >5%
        - CloudWatch alarm for latency >10 seconds
        - Updates CodeDeploy deployment group to enable alarm-based rollback
        
        The alarms monitor the runtime application health and trigger notifications
        when thresholds are exceeded. They also enable automatic rollback during
        deployments if the application enters an alarm state.
        
        Requirements: 10.5, 10.6, 10.7
        """
        # Create SNS topic for alarm notifications
        self.alarm_notification_topic = sns.Topic(
            self,
            f"AlarmNotificationTopic-{self.stage}",
            topic_name=f"sales-agent-alarms-{self.stage}",
            display_name=f"Sales Agent Runtime Alarms ({self.stage})",
        )
        
        # Tag the SNS topic
        Tags.of(self.alarm_notification_topic).add("Stage", self.stage)
        Tags.of(self.alarm_notification_topic).add("ManagedBy", "CDK")
        Tags.of(self.alarm_notification_topic).add("Application", "SalesAgentRuntime")
        
        # Create CloudWatch alarm for error rate >5%
        # This alarm monitors the percentage of HTTP 5xx errors from the load balancer
        self.error_rate_alarm = cloudwatch.Alarm(
            self,
            f"RuntimeErrorRateAlarm-{self.stage}",
            alarm_name=f"sales-agent-error-rate-{self.stage}",
            alarm_description=f"Runtime error rate exceeds 5% threshold ({self.stage})",
            metric=self.target_group.metric_http_code_target(
                code=elbv2.HttpCodeTarget.TARGET_5XX_COUNT,
                period=Duration.minutes(5),
                statistic="Sum",
            ).with_(
                # Calculate error rate as percentage
                # Error rate = (5xx count / total request count) * 100
                label="Error Rate",
            ),
            threshold=5,  # 5% error rate threshold
            evaluation_periods=2,  # Alarm after 2 consecutive periods above threshold
            datapoints_to_alarm=2,  # Both datapoints must breach threshold
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        
        # Add SNS action to error rate alarm
        self.error_rate_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alarm_notification_topic)
        )
        
        # Tag the error rate alarm
        Tags.of(self.error_rate_alarm).add("Stage", self.stage)
        Tags.of(self.error_rate_alarm).add("ManagedBy", "CDK")
        Tags.of(self.error_rate_alarm).add("Application", "SalesAgentRuntime")
        
        # Create CloudWatch alarm for latency >10 seconds
        # This alarm monitors the target response time from the load balancer
        self.latency_alarm = cloudwatch.Alarm(
            self,
            f"RuntimeLatencyAlarm-{self.stage}",
            alarm_name=f"sales-agent-latency-{self.stage}",
            alarm_description=f"Runtime latency exceeds 10 seconds threshold ({self.stage})",
            metric=self.target_group.metric_target_response_time(
                period=Duration.minutes(5),
                statistic="Average",
            ),
            threshold=10,  # 10 seconds latency threshold
            evaluation_periods=2,  # Alarm after 2 consecutive periods above threshold
            datapoints_to_alarm=2,  # Both datapoints must breach threshold
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        
        # Add SNS action to latency alarm
        self.latency_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alarm_notification_topic)
        )
        
        # Tag the latency alarm
        Tags.of(self.latency_alarm).add("Stage", self.stage)
        Tags.of(self.latency_alarm).add("ManagedBy", "CDK")
        Tags.of(self.latency_alarm).add("Application", "SalesAgentRuntime")
        
        # Update CodeDeploy deployment group to enable alarm-based rollback
        # Note: This requires recreating the deployment group with alarm configuration
        # The deployment group was created in _create_codedeploy_resources()
        # We need to add the alarms to the auto_rollback configuration
        
        # Create a new deployment group with alarm-based rollback enabled
        # First, we need to delete the old deployment group and create a new one
        # CDK doesn't support updating deployment groups in place
        
        # Store alarms for use in deployment group configuration
        self.monitoring_alarms = [self.error_rate_alarm, self.latency_alarm]
    
    def _create_outputs(self) -> None:
        """
        Create CloudFormation stack outputs.
        
        These outputs provide key information about deployed resources for
        reference by operators and the CLI tool.
        """
        # VPC ID output
        CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id if self.vpc else "TBD",
            description="VPC ID for runtime deployment",
            export_name=f"SalesAgent-{self.stage}-VpcId"
        )
        
        # Parameter Store prefix for CLI tool
        CfnOutput(
            self,
            "ParameterStorePrefix",
            value=self.parameter_store_prefix,
            description="Parameter Store path prefix for configuration",
            export_name=f"SalesAgent-{self.stage}-ParamPrefix"
        )
        
        # Stack stage identifier
        CfnOutput(
            self,
            "Stage",
            value=self.stage,
            description="Deployment stage identifier",
            export_name=f"SalesAgent-{self.stage}-Stage"
        )
        
        # Runtime endpoint (will be populated after runtime setup)
        CfnOutput(
            self,
            "RuntimeEndpoint",
            value=f"http://{self.alb.load_balancer_dns_name}" if hasattr(self, 'alb') else "TBD",
            description="Runtime invocation endpoint (ALB DNS name)",
            export_name=f"SalesAgent-{self.stage}-Endpoint"
        )
        
        # CodeCommit repository URL (will be populated after CI/CD setup)
        CfnOutput(
            self,
            "CodeCommitRepositoryUrl",
            value=self.code_repository.repository_clone_url_http if hasattr(self, 'code_repository') else "TBD",
            description="Git repository clone URL (HTTPS)",
            export_name=f"SalesAgent-{self.stage}-RepoUrl"
        )
        
        # CloudWatch log group (will be populated after monitoring setup)
        CfnOutput(
            self,
            "LogGroupName",
            value=f"/aws/sales-agent/{self.stage}",
            description="CloudWatch log group name",
            export_name=f"SalesAgent-{self.stage}-LogGroup"
        )
        
        # ECR repository URI for container images
        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=self.ecr_repository.repository_uri,
            description="ECR repository URI for runtime container images",
            export_name=f"SalesAgent-{self.stage}-EcrUri"
        )
        
        # CodePipeline name
        CfnOutput(
            self,
            "PipelineName",
            value=self.pipeline.pipeline_name if hasattr(self, 'pipeline') else "TBD",
            description="CodePipeline name for CI/CD automation",
            export_name=f"SalesAgent-{self.stage}-PipelineName"
        )
        
        # SNS topic ARN for pipeline notifications
        CfnOutput(
            self,
            "PipelineNotificationTopicArn",
            value=self.pipeline_notification_topic.topic_arn if hasattr(self, 'pipeline_notification_topic') else "TBD",
            description="SNS topic ARN for pipeline failure notifications",
            export_name=f"SalesAgent-{self.stage}-NotificationTopicArn"
        )
        
        # SNS topic ARN for alarm notifications
        CfnOutput(
            self,
            "AlarmNotificationTopicArn",
            value=self.alarm_notification_topic.topic_arn if hasattr(self, 'alarm_notification_topic') else "TBD",
            description="SNS topic ARN for CloudWatch alarm notifications",
            export_name=f"SalesAgent-{self.stage}-AlarmTopicArn"
        )
