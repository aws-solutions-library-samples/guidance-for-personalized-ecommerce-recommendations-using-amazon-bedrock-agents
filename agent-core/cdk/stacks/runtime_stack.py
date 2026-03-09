"""
Runtime Stack for compute resources.

This stack creates:
- ECS Fargate service for runtime containers
- Application Load Balancer
- CloudWatch log groups
- CloudWatch alarms
- SNS topics for notifications
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    Tags,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
)
from constructs import Construct
from typing import Optional


class RuntimeStack(Stack):
    """
    Runtime stack that creates compute resources for the Sales Agent.
    
    This stack is deployed by CodeBuild after InfrastructureStack.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        vpc_id: str,
        ecr_repository_uri: str,
        runtime_role_arn: str,
        **kwargs
    ) -> None:
        """
        Initialize the Runtime Stack.
        
        Args:
            scope: CDK scope
            construct_id: Stack identifier
            stage: Deployment stage (dev, staging, prod, etc.)
            vpc_id: VPC ID from InfrastructureStack
            ecr_repository_uri: ECR repository URI from InfrastructureStack
            runtime_role_arn: Runtime IAM role ARN from InfrastructureStack
        """
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage
        
        # Import VPC using from_lookup to automatically discover subnets
        self.vpc = ec2.Vpc.from_lookup(
            self,
            "Vpc",
            vpc_id=vpc_id,
        )
        
        # Import runtime role
        self.runtime_role = iam.Role.from_role_arn(
            self, "RuntimeRole", runtime_role_arn
        )
        
        # Store ECR repository URI
        self.ecr_repository_uri = ecr_repository_uri
        
        # Create ECS cluster
        self.cluster = self._create_cluster()
        
        # Create Fargate service
        self.service = self._create_fargate_service()
        
        # Create CloudWatch alarms
        self._create_alarms()
    
    def _create_cluster(self) -> ecs.Cluster:
        """
        Create ECS cluster for runtime containers.
        
        Returns:
            ECS cluster instance
        """
        cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"sales-agent-{self.stage}",
            vpc=self.vpc,
            container_insights=True,
        )
        
        Tags.of(cluster).add("Stage", self.stage)
        
        return cluster
    
    def _create_fargate_service(self) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        """
        Create Fargate service with Application Load Balancer.
        
        Returns:
            Fargate service instance
        """
        # Create log group without retention policy to allow automatic deletion
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/aws/sales-agent/{self.stage}",
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        Tags.of(log_group).add("Stage", self.stage)
        
        # Create task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"sales-agent-{self.stage}",
            cpu=1024,  # 1 vCPU
            memory_limit_mib=2048,  # 2 GB
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            task_role=self.runtime_role,
            execution_role=self.runtime_role,
        )
        
        # Add container
        container = task_definition.add_container(
            "RuntimeContainer",
            container_name="sales-agent-runtime",
            image=ecs.ContainerImage.from_registry(
                f"{self.ecr_repository_uri}:latest"
            ),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="runtime",
                log_group=log_group,
            ),
            environment={
                "STAGE": self.stage,
                "AWS_DEFAULT_REGION": self.region,
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "exit 0"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )
        
        # Expose port 8080 (BedrockAgentCore standard port per AWS documentation)
        container.add_port_mappings(
            ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP),
        )
        
        # Create Fargate service with ALB
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            service_name=f"sales-agent-{self.stage}",
            cluster=self.cluster,
            task_definition=task_definition,
            desired_count=1,
            public_load_balancer=False,  # Internal ALB
            task_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),  # Enable automatic rollback
        )
        
        # Configure health check - use /ping endpoint required by BedrockAgentCore
        service.target_group.configure_health_check(
            path="/ping",
            interval=Duration.seconds(10),  # Check every 10 seconds (reduced from 30)
            timeout=Duration.seconds(5),     # 5 second timeout
            healthy_threshold_count=2,       # 2 successful checks to be healthy
            unhealthy_threshold_count=2,     # 2 failed checks to be unhealthy (reduced from 5)
        )
        
        Tags.of(service.service).add("Stage", self.stage)
        
        # Output service endpoint
        CfnOutput(
            self,
            "ServiceEndpoint",
            value=service.load_balancer.load_balancer_dns_name,
            description="Runtime service endpoint",
            export_name=f"SalesAgent-{self.stage}-ServiceEndpoint",
        )
        
        CfnOutput(
            self,
            "LogGroupName",
            value=log_group.log_group_name,
            description="CloudWatch log group name",
            export_name=f"SalesAgent-{self.stage}-LogGroupName",
        )
        
        return service

    
    def _create_alarms(self) -> None:
        """
        Create CloudWatch alarms for monitoring runtime health.
        """
        # Create SNS topic for alarm notifications
        alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"sales-agent-alarms-{self.stage}",
            display_name=f"Sales Agent Alarms - {self.stage}",
        )
        
        Tags.of(alarm_topic).add("Stage", self.stage)
        
        # Output SNS topic ARN
        CfnOutput(
            self,
            "AlarmTopicArn",
            value=alarm_topic.topic_arn,
            description="SNS topic ARN for alarm notifications",
            export_name=f"SalesAgent-{self.stage}-AlarmTopicArn",
        )
        
        # Alarm for high error rate (>5%)
        error_rate_alarm = cloudwatch.Alarm(
            self,
            "ErrorRateAlarm",
            alarm_name=f"sales-agent-error-rate-{self.stage}",
            alarm_description=f"Error rate exceeds 5% for {self.stage}",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="TargetResponseTime",
                dimensions_map={
                    "ServiceName": self.service.service.service_name,
                    "ClusterName": self.cluster.cluster_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        
        error_rate_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        
        # Alarm for high latency (>10 seconds)
        latency_alarm = cloudwatch.Alarm(
            self,
            "LatencyAlarm",
            alarm_name=f"sales-agent-latency-{self.stage}",
            alarm_description=f"Response time exceeds 10 seconds for {self.stage}",
            metric=self.service.target_group.metric_target_response_time(
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        
        latency_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        
        # Alarm for unhealthy targets
        unhealthy_target_alarm = cloudwatch.Alarm(
            self,
            "UnhealthyTargetAlarm",
            alarm_name=f"sales-agent-unhealthy-targets-{self.stage}",
            alarm_description=f"Unhealthy targets detected for {self.stage}",
            metric=self.service.target_group.metric_unhealthy_host_count(
                statistic="Average",
                period=Duration.minutes(1),
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        
        unhealthy_target_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        
        Tags.of(error_rate_alarm).add("Stage", self.stage)
        Tags.of(latency_alarm).add("Stage", self.stage)
        Tags.of(unhealthy_target_alarm).add("Stage", self.stage)
