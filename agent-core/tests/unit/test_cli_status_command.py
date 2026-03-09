"""
Unit tests for CLI status command.

Tests the status command for displaying runtime deployment status.

**Validates: Requirements 5.9**
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from botocore.exceptions import ClientError
from click.testing import CliRunner

# Import CLI components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../cli'))

from sales_agent_cli import cli


class TestStatusCommand:
    """Test status command."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_success(self, mock_boto_client):
        """Test successful status retrieval."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        mock_ecs = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        # Mock CloudFormation stack
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'SalesAgentRuntimeStack-dev',
                'StackStatus': 'UPDATE_COMPLETE',
                'LastUpdatedTime': datetime(2024, 1, 1, 10, 0, 0),
                'Outputs': [
                    {
                        'OutputKey': 'RuntimeEndpoint',
                        'OutputValue': 'http://example-alb.us-east-1.elb.amazonaws.com'
                    },
                    {
                        'OutputKey': 'ECSClusterName',
                        'OutputValue': 'sales-agent-cluster-dev'
                    },
                    {
                        'OutputKey': 'ECSServiceName',
                        'OutputValue': 'sales-agent-service-dev'
                    }
                ]
            }]
        }
        
        # Mock ECS service
        mock_ecs.describe_services.return_value = {
            'services': [{
                'serviceName': 'sales-agent-service-dev',
                'status': 'ACTIVE',
                'runningCount': 2,
                'desiredCount': 2,
                'deployments': [{
                    'status': 'PRIMARY',
                    'taskDefinition': 'arn:aws:ecs:us-east-1:123456789012:task-definition/sales-agent-dev:5',
                    'createdAt': datetime(2024, 1, 1, 10, 0, 0)
                }]
            }]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            elif service_name == 'ecs':
                return mock_ecs
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 0
        assert 'Runtime Status for stage: dev' in result.output
        assert 'Stack Status: UPDATE_COMPLETE' in result.output
        assert 'Service Status: ACTIVE' in result.output
        assert 'Running Tasks: 2/2' in result.output
        assert 'Endpoint: http://example-alb.us-east-1.elb.amazonaws.com' in result.output
        assert 'Version: 5' in result.output
        assert 'Last Deployment: 2024-01-01' in result.output
        assert 'Health: HEALTHY' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_stack_not_found(self, mock_boto_client):
        """Test status when stack doesn't exist."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        mock_cfn.describe_stacks.side_effect = ClientError(
            {'Error': {'Code': 'ValidationError', 'Message': 'Stack does not exist'}},
            'DescribeStacks'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 1
        assert 'Stack not found for stage: dev' in result.output
        assert 'deploy.sh --stage dev' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_unhealthy_service(self, mock_boto_client):
        """Test status with unhealthy service."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        mock_ecs = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'SalesAgentRuntimeStack-dev',
                'StackStatus': 'UPDATE_COMPLETE',
                'LastUpdatedTime': datetime(2024, 1, 1, 10, 0, 0),
                'Outputs': [
                    {
                        'OutputKey': 'ECSClusterName',
                        'OutputValue': 'sales-agent-cluster-dev'
                    },
                    {
                        'OutputKey': 'ECSServiceName',
                        'OutputValue': 'sales-agent-service-dev'
                    }
                ]
            }]
        }
        
        # Mock unhealthy ECS service
        mock_ecs.describe_services.return_value = {
            'services': [{
                'serviceName': 'sales-agent-service-dev',
                'status': 'ACTIVE',
                'runningCount': 0,
                'desiredCount': 2,
                'deployments': [{
                    'status': 'PRIMARY',
                    'taskDefinition': 'arn:aws:ecs:us-east-1:123456789012:task-definition/sales-agent-dev:3',
                    'createdAt': datetime(2024, 1, 1, 10, 0, 0)
                }]
            }]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            elif service_name == 'ecs':
                return mock_ecs
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 0
        assert 'Running Tasks: 0/2' in result.output
        assert 'Health: UNHEALTHY' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_stack_in_progress(self, mock_boto_client):
        """Test status with stack update in progress."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'SalesAgentRuntimeStack-dev',
                'StackStatus': 'UPDATE_IN_PROGRESS',
                'LastUpdatedTime': datetime(2024, 1, 1, 10, 0, 0),
                'Outputs': []
            }]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 0
        assert 'Stack Status: UPDATE_IN_PROGRESS' in result.output
        assert 'Deployment in progress' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_stack_failed(self, mock_boto_client):
        """Test status with failed stack."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'SalesAgentRuntimeStack-dev',
                'StackStatus': 'UPDATE_ROLLBACK_COMPLETE',
                'LastUpdatedTime': datetime(2024, 1, 1, 10, 0, 0),
                'StackStatusReason': 'Resource creation failed',
                'Outputs': []
            }]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 0
        assert 'Stack Status: UPDATE_ROLLBACK_COMPLETE' in result.output
        assert 'Resource creation failed' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_access_denied(self, mock_boto_client):
        """Test status with access denied error."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        mock_cfn.describe_stacks.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'DescribeStacks'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 1
        assert 'Access denied' in result.output
        assert 'cloudformation:DescribeStacks' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_status_multiple_deployments(self, mock_boto_client):
        """Test status with multiple deployments (blue/green)."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_cfn = Mock()
        mock_ecs = Mock()
        
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'SalesAgentRuntimeStack-dev',
                'StackStatus': 'UPDATE_COMPLETE',
                'LastUpdatedTime': datetime(2024, 1, 1, 10, 0, 0),
                'Outputs': [
                    {
                        'OutputKey': 'ECSClusterName',
                        'OutputValue': 'sales-agent-cluster-dev'
                    },
                    {
                        'OutputKey': 'ECSServiceName',
                        'OutputValue': 'sales-agent-service-dev'
                    }
                ]
            }]
        }
        
        # Mock ECS service with multiple deployments
        mock_ecs.describe_services.return_value = {
            'services': [{
                'serviceName': 'sales-agent-service-dev',
                'status': 'ACTIVE',
                'runningCount': 4,
                'desiredCount': 4,
                'deployments': [
                    {
                        'status': 'PRIMARY',
                        'taskDefinition': 'arn:aws:ecs:us-east-1:123456789012:task-definition/sales-agent-dev:6',
                        'createdAt': datetime(2024, 1, 1, 11, 0, 0),
                        'runningCount': 2
                    },
                    {
                        'status': 'ACTIVE',
                        'taskDefinition': 'arn:aws:ecs:us-east-1:123456789012:task-definition/sales-agent-dev:5',
                        'createdAt': datetime(2024, 1, 1, 10, 0, 0),
                        'runningCount': 2
                    }
                ]
            }]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'cloudformation':
                return mock_cfn
            elif service_name == 'ecs':
                return mock_ecs
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'status'
        ])
        
        assert result.exit_code == 0
        assert 'Version: 6' in result.output
        assert 'Deployment in progress' in result.output or 'PRIMARY' in result.output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
