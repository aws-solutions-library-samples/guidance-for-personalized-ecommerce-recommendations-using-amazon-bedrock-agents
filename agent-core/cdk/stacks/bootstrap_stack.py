"""
Bootstrap Stack for CodePipeline-based deployment.

This stack creates the minimal infrastructure needed to trigger automated deployment:
- CodeCommit repository for source code
- CodePipeline for CI/CD orchestration
- CodeBuild project for building and deploying
- S3 bucket for pipeline artifacts
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
    aws_codecommit as codecommit,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    aws_s3 as s3,
    aws_iam as iam,
)
from constructs import Construct
from typing import Optional


class BootstrapStack(Stack):
    """
    Bootstrap stack that creates CI/CD infrastructure for automated deployment.
    
    This stack solves the chicken-and-egg problem by creating the pipeline first,
    then the pipeline builds the Docker image and deploys the full infrastructure.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        item_table: str,
        user_table: str,
        aoss_endpoint: str,
        personalize_arn: str,
        vpc_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Initialize the Bootstrap Stack.
        
        Args:
            scope: CDK scope
            construct_id: Stack identifier
            stage: Deployment stage (dev, staging, prod, etc.)
            item_table: DynamoDB items table name
            user_table: DynamoDB users table name
            aoss_endpoint: OpenSearch Serverless endpoint
            personalize_arn: Personalize recommender ARN
            vpc_id: Optional existing VPC ID
        """
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage
        
        # CodeCommit repository for source code
        self.repository = codecommit.Repository(
            self,
            "Repository",
            repository_name=f"sales-agent-runtime-{stage}",
            description=f"Sales Agent runtime source code for {stage} environment",
        )
        
        # S3 bucket for pipeline artifacts
        self.artifact_bucket = s3.Bucket(
            self,
            "ArtifactBucket",
            bucket_name=f"sales-agent-artifacts-{stage}-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=True,
        )
        
        # IAM role for CodeBuild with deployment permissions
        self.build_role = iam.Role(
            self,
            "BuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            description=f"CodeBuild role for {stage} deployment",
            managed_policies=[
                # AdministratorAccess needed for CDK deployment
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
        )
        
        # CodeBuild project for deployment
        self.build_project = codebuild.Project(
            self,
            "BuildProject",
            project_name=f"sales-agent-deploy-{stage}",
            description=f"Build and deploy Sales Agent for {stage}",
            source=codebuild.Source.code_commit(repository=self.repository),
            environment=codebuild.BuildEnvironment(
                # ARM64 compute for native Graviton builds
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.LARGE,
                privileged=True,  # Required for Docker builds
            ),
            environment_variables={
                "STAGE": codebuild.BuildEnvironmentVariable(value=stage),
                "ITEM_TABLE": codebuild.BuildEnvironmentVariable(value=item_table),
                "USER_TABLE": codebuild.BuildEnvironmentVariable(value=user_table),
                "AOSS_ENDPOINT": codebuild.BuildEnvironmentVariable(value=aoss_endpoint),
                "PERSONALIZE_ARN": codebuild.BuildEnvironmentVariable(value=personalize_arn),
                "VPC_ID": codebuild.BuildEnvironmentVariable(value=vpc_id or ""),
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(
                    value=self.region
                ),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(
                    value=self.account
                ),
            },
            role=self.build_role,
            timeout=Duration.minutes(60),
        )
        
        # CodePipeline
        self.pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"sales-agent-pipeline-{stage}",
            artifact_bucket=self.artifact_bucket,
        )
        
        # Source stage - monitors CodeCommit repository
        source_output = codepipeline.Artifact("SourceOutput")
        self.pipeline.add_stage(
            stage_name="Source",
            actions=[
                codepipeline_actions.CodeCommitSourceAction(
                    action_name="CodeCommit",
                    repository=self.repository,
                    branch="main",
                    output=source_output,
                    trigger=codepipeline_actions.CodeCommitTrigger.EVENTS,
                )
            ],
        )
        
        # Build stage - runs CodeBuild project
        self.pipeline.add_stage(
            stage_name="Build",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="Deploy",
                    project=self.build_project,
                    input=source_output,
                )
            ],
        )
        
        # Stack outputs
        CfnOutput(
            self,
            "RepositoryUrl",
            value=self.repository.repository_clone_url_http,
            description="CodeCommit repository clone URL (HTTPS)",
            export_name=f"SalesAgent-{stage}-RepositoryUrl",
        )
        
        CfnOutput(
            self,
            "RepositoryName",
            value=self.repository.repository_name,
            description="CodeCommit repository name",
            export_name=f"SalesAgent-{stage}-RepositoryName",
        )
        
        CfnOutput(
            self,
            "PipelineName",
            value=self.pipeline.pipeline_name,
            description="CodePipeline name for status tracking",
            export_name=f"SalesAgent-{stage}-PipelineName",
        )
        
        CfnOutput(
            self,
            "BuildProjectName",
            value=self.build_project.project_name,
            description="CodeBuild project name",
            export_name=f"SalesAgent-{stage}-BuildProjectName",
        )
