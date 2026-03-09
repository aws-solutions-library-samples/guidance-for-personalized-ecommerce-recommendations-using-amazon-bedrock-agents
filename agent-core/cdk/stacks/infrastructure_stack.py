"""
Infrastructure Stack for core shared resources.

This stack creates:
- VPC (new or imported)
- IAM roles and policies  
- Parameter Store entries
- ECR repository
- AgentCore Memory configuration
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    Tags,
    RemovalPolicy,
    Duration,
    aws_ec2 as ec2,
    aws_ssm as ssm,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_bedrock as bedrock,
)
from constructs import Construct
from typing import Optional


class InfrastructureStack(Stack):
    """
    Infrastructure stack that creates core shared resources.
    
    This stack is deployed by CodeBuild before the RuntimeStack.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        vpc_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Initialize the Infrastructure Stack.
        
        Args:
            scope: CDK scope
            construct_id: Stack identifier
            stage: Deployment stage (dev, staging, prod, etc.)
            vpc_id: Optional existing VPC ID
        """
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage
        self.vpc_id = vpc_id
        
        # Setup VPC (create new or import existing)
        self.vpc = self._setup_vpc()
        
        # Create Parameter Store entries
        self._create_parameter_store()
        
        # Create ECR repository
        self.ecr_repository = self._create_ecr_repository()
        
        # Create runtime execution role
        self.runtime_role = self._create_runtime_role()
        
        # Create AgentCore Memory
        self.memory = self._create_memory()
    
    def _setup_vpc(self) -> ec2.IVpc:
        """
        Setup VPC - either import existing or create new.
        
        Returns:
            VPC instance (imported or newly created)
        """
        if self.vpc_id:
            # Import existing VPC
            vpc = ec2.Vpc.from_lookup(
                self,
                "ImportedVpc",
                vpc_id=self.vpc_id,
            )
            
            CfnOutput(
                self,
                "VpcId",
                value=vpc.vpc_id,
                description="Imported VPC ID",
                export_name=f"SalesAgent-{self.stage}-VpcId",
            )
        else:
            # Create new VPC
            vpc = ec2.Vpc(
                self,
                "Vpc",
                vpc_name=f"sales-agent-vpc-{self.stage}",
                ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
                max_azs=2,
                nat_gateways=2,
                subnet_configuration=[
                    # Public subnets for NAT gateways and load balancers
                    ec2.SubnetConfiguration(
                        name="Public",
                        subnet_type=ec2.SubnetType.PUBLIC,
                        cidr_mask=24,
                    ),
                    # Private subnets for runtime containers
                    ec2.SubnetConfiguration(
                        name="Private",
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                        cidr_mask=24,
                    ),
                ],
            )
            
            # Add VPC endpoints for AWS services
            vpc.add_gateway_endpoint(
                "DynamoDbEndpoint",
                service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            )
            
            vpc.add_gateway_endpoint(
                "S3Endpoint",
                service=ec2.GatewayVpcEndpointAwsService.S3,
            )
            
            vpc.add_interface_endpoint(
                "SsmEndpoint",
                service=ec2.InterfaceVpcEndpointAwsService.SSM,
            )
            
            CfnOutput(
                self,
                "VpcId",
                value=vpc.vpc_id,
                description="Created VPC ID",
                export_name=f"SalesAgent-{self.stage}-VpcId",
            )
        
        return vpc

    
    def _create_parameter_store(self) -> None:
        """
        Create Parameter Store entries for runtime configuration.
        
        All parameters use hierarchical naming: /sales-agent/{stage}/{key}
        """
        import os
        
        # Get parameter values from environment variables (set by CodeBuild)
        item_table = os.environ.get("ITEM_TABLE", "")
        user_table = os.environ.get("USER_TABLE", "")
        aoss_endpoint = os.environ.get("AOSS_ENDPOINT", "")
        personalize_arn = os.environ.get("PERSONALIZE_ARN", "")
        
        # Parameter Store prefix
        prefix = f"/sales-agent/{self.stage}"
        
        # Create parameters
        parameters = {
            "item_table": item_table,
            "user_table": user_table,
            "aoss_endpoint": aoss_endpoint,
            "recommender_arn": personalize_arn,
            "s3_bucket": f"sales-agent-images-{self.stage}",
        }
        
        for key, value in parameters.items():
            param = ssm.StringParameter(
                self,
                f"Param-{key}",
                parameter_name=f"{prefix}/{key}",
                string_value=value,
                description=f"Sales Agent {key} for {self.stage} stage",
                tier=ssm.ParameterTier.STANDARD,
            )
            
            # Tag parameter with stage
            Tags.of(param).add("Stage", self.stage)
        
        # Output parameter store prefix
        CfnOutput(
            self,
            "ParameterStorePrefix",
            value=prefix,
            description="Parameter Store prefix for this stage",
            export_name=f"SalesAgent-{self.stage}-ParameterPrefix",
        )

    
    def _create_ecr_repository(self) -> ecr.Repository:
        """
        Create ECR repository for container images.
        
        Returns:
            ECR repository instance
        """
        repository = ecr.Repository(
            self,
            "RuntimeRepository",
            repository_name=f"sales-agent-runtime-{self.stage}",
            image_scan_on_push=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep last 10 images",
                    max_image_count=10,
                )
            ],
        )
        
        # Tag repository with stage
        Tags.of(repository).add("Stage", self.stage)
        
        # Output repository URI
        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=repository.repository_uri,
            description="ECR repository URI for runtime images",
            export_name=f"SalesAgent-{self.stage}-EcrRepositoryUri",
        )
        
        CfnOutput(
            self,
            "EcrRepositoryName",
            value=repository.repository_name,
            description="ECR repository name",
            export_name=f"SalesAgent-{self.stage}-EcrRepositoryName",
        )
        
        return repository

    
    def _create_runtime_role(self) -> iam.Role:
        """
        Create IAM role for runtime execution with least-privilege policies.
        
        Returns:
            IAM role instance
        """
        import os
        
        # Get resource ARNs from environment
        item_table = os.environ.get("ITEM_TABLE", "")
        user_table = os.environ.get("USER_TABLE", "")
        aoss_endpoint = os.environ.get("AOSS_ENDPOINT", "")
        personalize_arn = os.environ.get("PERSONALIZE_ARN", "")
        
        # Extract collection ID from AOSS endpoint
        # Format: https://<collection-id>.us-east-1.aoss.amazonaws.com
        collection_id = aoss_endpoint.split("//")[1].split(".")[0] if aoss_endpoint else "*"
        
        # Create execution role
        # Note: Role must be assumable by both ECS tasks and Bedrock for Knowledge Base
        role = iam.Role(
            self,
            "RuntimeRole",
            role_name=f"sales-agent-runtime-{self.stage}",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                iam.ServicePrincipal("bedrock.amazonaws.com"),
            ),
            description=f"Execution role for Sales Agent runtime - {self.stage}",
        )
        
        # DynamoDB permissions - scoped to specific tables
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:Query",
                    "dynamodb:GetItem",
                    "dynamodb:BatchGetItem",
                ],
                resources=[
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{item_table}",
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{user_table}",
                ],
            )
        )
        
        # OpenSearch Serverless permissions - scoped to specific collection
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aoss:APIAccessAll",
                ],
                resources=[
                    f"arn:aws:aoss:{self.region}:{self.account}:collection/{collection_id}",
                ],
            )
        )
        
        # Personalize permissions - scoped to specific recommender
        if personalize_arn:
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "personalize:GetRecommendations",
                    ],
                    resources=[personalize_arn],
                )
            )
        
        # Bedrock permissions - scoped to specific models
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-image-v1",
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0",
                ],
            )
        )
        
        # Parameter Store permissions - scoped to stage prefix
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/sales-agent/{self.stage}/*",
                ],
            )
        )
        
        # AgentCore Memory permissions - will be added after memory creation
        # Placeholder for now
        
        # CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sales-agent/{self.stage}/*",
                ],
            )
        )
        
        # ECR permissions for pulling container images
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                ],
                resources=["*"],  # GetAuthorizationToken doesn't support resource-level permissions
            )
        )
        
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                resources=[
                    f"arn:aws:ecr:{self.region}:{self.account}:repository/sales-agent-runtime-{self.stage}",
                ],
            )
        )
        
        # Tag role with stage
        Tags.of(role).add("Stage", self.stage)
        
        # Output role ARN
        CfnOutput(
            self,
            "RuntimeRoleArn",
            value=role.role_arn,
            description="Runtime execution role ARN",
            export_name=f"SalesAgent-{self.stage}-RuntimeRoleArn",
        )
        
        return role

    
    def _create_memory(self) -> str:
        """
        Create AgentCore Memory configuration for conversation history.
        
        Returns:
            Memory ID string
        """
        # AgentCore Memory is managed by the Bedrock Agent runtime
        # We create a memory identifier that the runtime will use
        memory_id = f"sales-agent-memory-{self.stage}"
        
        # Grant runtime role permissions to access Bedrock Agent Memory APIs
        self.runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeAgent",
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate",
                ],
                resources=["*"],  # Memory resources are created dynamically by AgentCore
            )
        )
        
        # Store memory ID in Parameter Store
        ssm.StringParameter(
            self,
            "MemoryIdParam",
            parameter_name=f"/sales-agent/{self.stage}/memory_id",
            string_value=memory_id,
            description=f"AgentCore Memory ID for {self.stage}",
        )
        
        # Output memory ID
        CfnOutput(
            self,
            "MemoryId",
            value=memory_id,
            description="AgentCore Memory ID",
            export_name=f"SalesAgent-{self.stage}-MemoryId",
        )
        
        return memory_id
