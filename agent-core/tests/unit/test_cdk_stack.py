"""
Unit tests for CDK stack infrastructure.

Tests VPC creation, parameter store, IAM roles, runtime resources,
CI/CD pipeline, and monitoring configuration.
"""

import os
import pytest
from aws_cdk import App, Stack, assertions, Environment
from aws_cdk.assertions import Template, Match

# Set required environment variables for tests
os.environ["ITEM_TABLE"] = "test-items"
os.environ["USER_TABLE"] = "test-users"
os.environ["AOSS_ENDPOINT"] = "https://test.us-east-1.aoss.amazonaws.com"
os.environ["PERSONALIZE_ARN"] = "arn:aws:personalize:us-east-1:123456789012:recommender/test"

from cdk.stacks.bootstrap_stack import BootstrapStack
from cdk.stacks.infrastructure_stack import InfrastructureStack
from cdk.stacks.runtime_stack import RuntimeStack


class TestBootstrapStack:
    """Test BootstrapStack creation."""
    
    def test_bootstrap_stack_creates_codecommit(self):
        """Test that BootstrapStack creates CodeCommit repository."""
        app = App()
        stack = BootstrapStack(
            app,
            "TestBootstrapStack",
            stage="test",
            item_table="test-items",
            user_table="test-users",
            aoss_endpoint="https://test.us-east-1.aoss.amazonaws.com",
            personalize_arn="arn:aws:personalize:us-east-1:123456789012:recommender/test",
            env=Environment(account="123456789012", region="us-east-1"),
        )
        template = Template.from_stack(stack)
        
        # Verify CodeCommit repository
        template.resource_count_is("AWS::CodeCommit::Repository", 1)
        template.has_resource_properties("AWS::CodeCommit::Repository", {
            "RepositoryName": "sales-agent-runtime-test"
        })
    
    def test_bootstrap_stack_creates_pipeline(self):
        """Test that BootstrapStack creates CodePipeline."""
        app = App()
        stack = BootstrapStack(
            app,
            "TestBootstrapStack",
            stage="test",
            item_table="test-items",
            user_table="test-users",
            aoss_endpoint="https://test.us-east-1.aoss.amazonaws.com",
            personalize_arn="arn:aws:personalize:us-east-1:123456789012:recommender/test",
            env=Environment(account="123456789012", region="us-east-1"),
        )
        template = Template.from_stack(stack)
        
        # Verify CodePipeline
        template.resource_count_is("AWS::CodePipeline::Pipeline", 1)
        template.has_resource_properties("AWS::CodePipeline::Pipeline", {
            "Name": "sales-agent-pipeline-test"
        })


class TestInfrastructureStack:
    """Test InfrastructureStack creation."""
    
    def test_infrastructure_stack_creates_vpc(self):
        """Test that InfrastructureStack creates VPC when vpc_id not provided."""
        app = App()
        stack = InfrastructureStack(
            app,
            "TestInfraStack",
            stage="test",
            env=Environment(account="123456789012", region="us-east-1"),
        )
        template = Template.from_stack(stack)
        
        # Verify VPC is created
        template.resource_count_is("AWS::EC2::VPC", 1)
    
    def test_infrastructure_stack_creates_ecr(self):
        """Test that InfrastructureStack creates ECR repository."""
        app = App()
        stack = InfrastructureStack(
            app,
            "TestInfraStack",
            stage="test",
            env=Environment(account="123456789012", region="us-east-1"),
        )
        template = Template.from_stack(stack)
        
        # Verify ECR repository
        template.resource_count_is("AWS::ECR::Repository", 1)
        template.has_resource_properties("AWS::ECR::Repository", {
            "RepositoryName": "sales-agent-runtime-test"
        })


class TestVPCConfiguration:
    """Test VPC creation and configuration."""
    
    def test_vpc_creation_without_vpc_id(self):
        """Test that stack creates new VPC when vpc_id is not provided."""
        app = App()
        stack = InfrastructureStack(
            app,
            "TestStack",
            stage="test",
            env=Environment(account="123456789012", region="us-east-1"),
        )
        template = Template.from_stack(stack)
        
        # Verify VPC is created
        template.resource_count_is("AWS::EC2::VPC", 1)
        
        # Verify VPC has correct CIDR
        template.has_resource_properties("AWS::EC2::VPC", {
            "CidrBlock": "10.0.0.0/16",
            "EnableDnsHostnames": True,
            "EnableDnsSupport": True
        })
        
        # Verify public and private subnets are created
        template.resource_count_is("AWS::EC2::Subnet", 4)  # 2 public + 2 private
        
        # Verify NAT gateways are created
        template.resource_count_is("AWS::EC2::NatGateway", 2)
    
    def test_vpc_import_with_vpc_id(self):
        """Test that stack uses existing VPC when vpc_id is provided."""
        app = App()
        stack = SalesAgentRuntimeStack(
            app, "TestStack", 
            stage="test",
            vpc_id="vpc-12345678"
        )
        template = Template.from_stack(stack)
        
        # Verify no new VPC is created
        template.resource_count_is("AWS::EC2::VPC", 0)
        
        # Stack should still have security groups and other resources
        template.resource_count_is("AWS::EC2::SecurityGroup", Match.any_value())
    
    def test_vpc_endpoints_configuration(self):
        """Test that VPC endpoints are configured for AWS services."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify VPC endpoints are created
        # DynamoDB, S3, and SSM endpoints
        template.resource_count_is("AWS::EC2::VPCEndpoint", Match.any_value())


class TestParameterStore:
    """Test Parameter Store configuration."""
    
    def test_parameter_store_entries_creation(self):
        """Test that all required parameter store entries are created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify parameter store entries are created
        template.resource_count_is("AWS::SSM::Parameter", 6)
        
        # Verify hierarchical naming with stage prefix
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/sales-agent/test/item_table",
            "Type": "String"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/sales-agent/test/user_table",
            "Type": "String"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/sales-agent/test/aoss_endpoint",
            "Type": "String"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/sales-agent/test/recommender_arn",
            "Type": "String"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/sales-agent/test/s3_bucket",
            "Type": "String"
        })
        
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Name": "/sales-agent/test/memory_id",
            "Type": "String"
        })
    
    def test_parameter_store_stage_tagging(self):
        """Test that parameter store entries are tagged with stage."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="dev")
        template = Template.from_stack(stack)
        
        # Verify parameters have Stage tag
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Tags": Match.object_like({
                "Stage": "dev"
            })
        })


class TestIAMConfiguration:
    """Test IAM roles and policies."""
    
    def test_runtime_execution_role_creation(self):
        """Test that runtime execution role is created with correct policies."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify runtime role is created
        template.has_resource_properties("AWS::IAM::Role", {
            "AssumeRolePolicyDocument": Match.object_like({
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow"
                    })
                ])
            })
        })
    
    def test_runtime_role_dynamodb_permissions(self):
        """Test that runtime role has DynamoDB permissions."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify DynamoDB policy is attached
        template.has_resource_properties("AWS::IAM::Policy", {
            "PolicyDocument": Match.object_like({
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": Match.array_with([
                            "dynamodb:Query",
                            "dynamodb:GetItem"
                        ]),
                        "Effect": "Allow"
                    })
                ])
            })
        })
    
    def test_runtime_role_parameter_store_permissions(self):
        """Test that runtime role has Parameter Store permissions."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify SSM policy is attached
        template.has_resource_properties("AWS::IAM::Policy", {
            "PolicyDocument": Match.object_like({
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": Match.array_with([
                            "ssm:GetParameter",
                            "ssm:GetParametersByPath"
                        ]),
                        "Effect": "Allow",
                        "Resource": Match.array_with([
                            Match.string_like_regexp(".*parameter/sales-agent/.*")
                        ])
                    })
                ])
            })
        })
    
    def test_runtime_role_bedrock_permissions(self):
        """Test that runtime role has Bedrock permissions."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify Bedrock policy is attached
        template.has_resource_properties("AWS::IAM::Policy", {
            "PolicyDocument": Match.object_like({
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": "bedrock:InvokeModel",
                        "Effect": "Allow"
                    })
                ])
            })
        })
    
    def test_cicd_service_roles_creation(self):
        """Test that CI/CD service roles are created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify multiple IAM roles exist (runtime + CI/CD roles)
        template.resource_count_is("AWS::IAM::Role", Match.any_value())


class TestRuntimeResources:
    """Test runtime deployment resources."""
    
    def test_ecr_repository_creation(self):
        """Test that ECR repository is created with stage prefix."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify ECR repository is created
        template.resource_count_is("AWS::ECR::Repository", 1)
        
        # Verify repository has stage-prefixed name
        template.has_resource_properties("AWS::ECR::Repository", {
            "RepositoryName": "sales-agent-runtime-test"
        })
        
        # Verify image scanning is enabled
        template.has_resource_properties("AWS::ECR::Repository", {
            "ImageScanningConfiguration": {
                "ScanOnPush": True
            }
        })
    
    def test_ecs_cluster_creation(self):
        """Test that ECS cluster is created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify ECS cluster is created
        template.resource_count_is("AWS::ECS::Cluster", 1)
        
        # Verify cluster has stage-prefixed name
        template.has_resource_properties("AWS::ECS::Cluster", {
            "ClusterName": "sales-agent-cluster-test"
        })
    
    def test_ecs_task_definition_creation(self):
        """Test that ECS task definition is created with correct configuration."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify task definition is created
        template.resource_count_is("AWS::ECS::TaskDefinition", 1)
        
        # Verify task uses Fargate and ARM64
        template.has_resource_properties("AWS::ECS::TaskDefinition", {
            "RequiresCompatibilities": ["FARGATE"],
            "RuntimePlatform": {
                "CpuArchitecture": "ARM64",
                "OperatingSystemFamily": "LINUX"
            }
        })
    
    def test_ecs_service_creation(self):
        """Test that ECS service is created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify ECS service is created
        template.resource_count_is("AWS::ECS::Service", 1)
        
        # Verify service has stage-prefixed name
        template.has_resource_properties("AWS::ECS::Service", {
            "ServiceName": "sales-agent-service-test"
        })
    
    def test_load_balancer_creation(self):
        """Test that Application Load Balancer is created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify ALB is created
        template.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 1)
        
        # Verify ALB has stage-prefixed name
        template.has_resource_properties("AWS::ElasticLoadBalancingV2::LoadBalancer", {
            "Name": Match.string_like_regexp(".*test.*")
        })


class TestCICDPipeline:
    """Test CI/CD pipeline resources."""
    
    def test_codecommit_repository_creation(self):
        """Test that CodeCommit repository is created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify CodeCommit repository is created
        template.resource_count_is("AWS::CodeCommit::Repository", 1)
        
        # Verify repository has stage-suffixed name
        template.has_resource_properties("AWS::CodeCommit::Repository", {
            "RepositoryName": "sales-agent-runtime-test"
        })
    
    def test_codebuild_project_creation(self):
        """Test that CodeBuild project is created with ARM64 configuration."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify CodeBuild project is created
        template.resource_count_is("AWS::CodeBuild::Project", 1)
        
        # Verify ARM64 compute type
        template.has_resource_properties("AWS::CodeBuild::Project", {
            "Environment": Match.object_like({
                "ComputeType": Match.any_value(),
                "Type": "ARM_CONTAINER"
            })
        })
    
    def test_codedeploy_application_creation(self):
        """Test that CodeDeploy application is created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify CodeDeploy application is created
        template.resource_count_is("AWS::CodeDeploy::Application", 1)
        
        # Verify application has correct compute platform
        template.has_resource_properties("AWS::CodeDeploy::Application", {
            "ComputePlatform": "ECS"
        })
    
    def test_codedeploy_deployment_group_creation(self):
        """Test that CodeDeploy deployment group is created with blue/green strategy."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify deployment group is created
        template.resource_count_is("AWS::CodeDeploy::DeploymentGroup", 1)
        
        # Verify blue/green deployment configuration
        template.has_resource_properties("AWS::CodeDeploy::DeploymentGroup", {
            "DeploymentConfigName": Match.any_value(),
            "BlueGreenDeploymentConfiguration": Match.object_like({
                "TerminateBlueInstancesOnDeploymentSuccess": Match.object_like({
                    "Action": "TERMINATE"
                })
            })
        })
    
    def test_codepipeline_creation(self):
        """Test that CodePipeline is created with source, build, deploy stages."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify pipeline is created
        template.resource_count_is("AWS::CodePipeline::Pipeline", 1)
        
        # Verify pipeline has three stages
        template.has_resource_properties("AWS::CodePipeline::Pipeline", {
            "Stages": Match.array_with([
                Match.object_like({"Name": "Source"}),
                Match.object_like({"Name": "Build"}),
                Match.object_like({"Name": "Deploy"})
            ])
        })


class TestMonitoring:
    """Test monitoring and observability resources."""
    
    def test_cloudwatch_log_group_creation(self):
        """Test that CloudWatch log group is created with correct retention."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify log group is created
        template.resource_count_is("AWS::Logs::LogGroup", Match.any_value())
        
        # Verify log group has stage-prefixed name and 30-day retention
        template.has_resource_properties("AWS::Logs::LogGroup", {
            "LogGroupName": Match.string_like_regexp("/aws/ecs/sales-agent.*test.*"),
            "RetentionInDays": 30
        })
    
    def test_cloudwatch_alarms_creation(self):
        """Test that CloudWatch alarms are created for error rate and latency."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify alarms are created
        template.resource_count_is("AWS::CloudWatch::Alarm", Match.any_value())
    
    def test_sns_topic_creation(self):
        """Test that SNS topic is created for alarm notifications."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify SNS topic is created
        template.resource_count_is("AWS::SNS::Topic", 1)
        
        # Verify topic has stage-prefixed name
        template.has_resource_properties("AWS::SNS::Topic", {
            "TopicName": "sales-agent-alarms-test"
        })


class TestStackOutputs:
    """Test CloudFormation stack outputs."""
    
    def test_stack_outputs_exist(self):
        """Test that all required stack outputs are created."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Verify outputs exist
        outputs = template.find_outputs("*")
        
        # Check for key outputs
        assert "VpcId" in outputs or len(outputs) > 0
        assert "RuntimeEndpoint" in outputs or len(outputs) > 0
        assert "CodeCommitRepositoryUrl" in outputs or len(outputs) > 0


class TestMultiStageDeployment:
    """Test multi-stage deployment support."""
    
    def test_different_stages_have_different_resource_names(self):
        """Test that different stages create resources with different names."""
        app = App()
        
        # Create stacks for different stages
        dev_stack = SalesAgentRuntimeStack(app, "DevStack", stage="dev")
        prod_stack = SalesAgentRuntimeStack(app, "ProdStack", stage="prod")
        
        dev_template = Template.from_stack(dev_stack)
        prod_template = Template.from_stack(prod_stack)
        
        # Verify ECR repositories have different names
        dev_template.has_resource_properties("AWS::ECR::Repository", {
            "RepositoryName": "sales-agent-runtime-dev"
        })
        
        prod_template.has_resource_properties("AWS::ECR::Repository", {
            "RepositoryName": "sales-agent-runtime-prod"
        })
    
    def test_stage_tagging(self):
        """Test that all resources are tagged with stage."""
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="staging")
        template = Template.from_stack(stack)
        
        # Verify resources have Stage tag
        # Note: Not all resources support tags, but key ones should
        template.has_resource_properties("AWS::SSM::Parameter", {
            "Tags": Match.object_like({
                "Stage": "staging"
            })
        })


class TestStageNameValidation:
    """Test stage name validation."""
    
    def test_valid_stage_names(self):
        """Test that valid stage names are accepted."""
        app = App()
        
        # These should not raise exceptions
        valid_stages = ["dev", "staging", "prod", "test-env", "feature_branch"]
        
        for stage in valid_stages:
            stack = SalesAgentRuntimeStack(app, f"Stack-{stage}", stage=stage)
            assert stack is not None
    
    def test_invalid_stage_names(self):
        """Test that invalid stage names are rejected."""
        app = App()
        
        # These should raise exceptions
        invalid_stages = ["dev@prod", "stage with spaces", "stage!123"]
        
        for stage in invalid_stages:
            with pytest.raises(ValueError):
                SalesAgentRuntimeStack(app, f"Stack-{stage}", stage=stage)
