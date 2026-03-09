"""
Unit tests for CloudWatch monitoring alarms.

Tests verify that CloudWatch alarms are created correctly with proper
configuration for error rate and latency monitoring.
"""

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template, Match
from cdk.stacks.sales_agent_stack import SalesAgentRuntimeStack


def test_alarm_sns_topic_created():
    """Verify SNS topic for alarm notifications is created."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify SNS topic exists with correct name
    template.has_resource_properties("AWS::SNS::Topic", {
        "TopicName": "sales-agent-alarms-test",
        "DisplayName": "Sales Agent Runtime Alarms (test)",
    })


def test_error_rate_alarm_created():
    """Verify CloudWatch alarm for error rate >5% is created."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify error rate alarm exists
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        "AlarmName": "sales-agent-error-rate-test",
        "AlarmDescription": "Runtime error rate exceeds 5% threshold (test)",
        "Threshold": 5,
        "EvaluationPeriods": 2,
        "DatapointsToAlarm": 2,
        "ComparisonOperator": "GreaterThanThreshold",
        "TreatMissingData": "notBreaching",
    })


def test_latency_alarm_created():
    """Verify CloudWatch alarm for latency >10 seconds is created."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify latency alarm exists
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        "AlarmName": "sales-agent-latency-test",
        "AlarmDescription": "Runtime latency exceeds 10 seconds threshold (test)",
        "Threshold": 10,
        "EvaluationPeriods": 2,
        "DatapointsToAlarm": 2,
        "ComparisonOperator": "GreaterThanThreshold",
        "TreatMissingData": "notBreaching",
    })


def test_alarms_have_sns_actions():
    """Verify alarms are configured to publish to SNS topic."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify alarms have SNS actions configured
    # Both error rate and latency alarms should have AlarmActions
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        "AlarmActions": Match.array_with([
            Match.object_like({
                "Ref": Match.string_like_regexp("AlarmNotificationTopic.*")
            })
        ])
    })


def test_codedeploy_deployment_group_has_alarm_rollback():
    """Verify CodeDeploy deployment group enables alarm-based rollback."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify deployment group has auto rollback configuration with deployment_in_alarm
    template.has_resource_properties("AWS::CodeDeploy::DeploymentGroup", {
        "AutoRollbackConfiguration": {
            "Enabled": True,
            "Events": Match.array_with([
                "DEPLOYMENT_FAILURE",
                "DEPLOYMENT_STOP_ON_ALARM",
                "DEPLOYMENT_STOP_ON_REQUEST",
            ])
        }
    })


def test_codedeploy_deployment_group_has_alarms():
    """Verify CodeDeploy deployment group references CloudWatch alarms."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify deployment group has alarm configuration
    template.has_resource_properties("AWS::CodeDeploy::DeploymentGroup", {
        "AlarmConfiguration": {
            "Enabled": True,
            "Alarms": Match.array_with([
                Match.object_like({
                    "Name": Match.any_value()
                })
            ])
        }
    })


def test_alarm_notification_topic_output():
    """Verify SNS topic ARN is exported as stack output."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify output exists for alarm notification topic ARN
    template.has_output("AlarmNotificationTopicArn", {
        "Description": "SNS topic ARN for CloudWatch alarm notifications",
        "Export": {
            "Name": "SalesAgent-test-AlarmTopicArn"
        }
    })


def test_alarms_tagged_correctly():
    """Verify alarms and SNS topic are tagged with Stage and ManagedBy."""
    app = App()
    stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
    template = Template.from_stack(stack)
    
    # Verify SNS topic has correct tags
    template.has_resource_properties("AWS::SNS::Topic", {
        "Tags": Match.array_with([
            {"Key": "Stage", "Value": "test"},
            {"Key": "ManagedBy", "Value": "CDK"},
            {"Key": "Application", "Value": "SalesAgentRuntime"},
        ])
    })
    
    # Verify alarms have correct tags
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        "Tags": Match.array_with([
            {"Key": "Stage", "Value": "test"},
            {"Key": "ManagedBy", "Value": "CDK"},
            {"Key": "Application", "Value": "SalesAgentRuntime"},
        ])
    })
