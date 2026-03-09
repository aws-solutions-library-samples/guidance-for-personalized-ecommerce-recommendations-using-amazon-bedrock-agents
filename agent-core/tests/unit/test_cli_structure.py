"""
Unit tests for CLI application structure.

Tests the basic CLI structure, initialization, and validation methods.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError

# Import CLI components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../cli'))

from sales_agent_cli import SalesAgentCLI


class TestSalesAgentCLIInit:
    """Test SalesAgentCLI initialization."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_init_creates_clients(self, mock_boto_client):
        """Test that __init__ creates AWS service clients."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_logs = Mock()
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            elif service_name == 'logs':
                return mock_logs
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        
        assert cli.stage == "test"
        assert cli.ssm == mock_ssm
        assert cli.sts == mock_sts
        assert cli.logs == mock_logs
    
    @patch('sales_agent_cli.boto3.client')
    def test_init_with_different_stages(self, mock_boto_client):
        """Test initialization with different stage names."""
        mock_boto_client.return_value = Mock()
        
        for stage in ["dev", "staging", "prod", "test-123", "feature_branch"]:
            cli = SalesAgentCLI(stage=stage)
            assert cli.stage == stage


class TestValidateCredentials:
    """Test credential validation method."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_validate_credentials_success(self, mock_boto_client):
        """Test successful credential validation."""
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            'Account': '123456789012',
            'UserId': 'FAKE-USER-ID-FOR-TESTING',
            'Arn': 'arn:aws:iam::123456789012:user/test'
        }
        
        def client_factory(service_name):
            if service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        result = cli.validate_credentials()
        
        assert result is True
        mock_sts.get_caller_identity.assert_called_once()
    
    @patch('sales_agent_cli.boto3.client')
    def test_validate_credentials_no_credentials(self, mock_boto_client):
        """Test credential validation fails with no credentials."""
        mock_sts = Mock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        
        def client_factory(service_name):
            if service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        
        with pytest.raises(SystemExit) as exc_info:
            cli.validate_credentials()
        
        assert exc_info.value.code == 1
    
    @patch('sales_agent_cli.boto3.client')
    def test_validate_credentials_client_error(self, mock_boto_client):
        """Test credential validation fails with client error."""
        mock_sts = Mock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {'Error': {'Code': 'InvalidClientTokenId', 'Message': 'Invalid token'}},
            'GetCallerIdentity'
        )
        
        def client_factory(service_name):
            if service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        
        with pytest.raises(SystemExit) as exc_info:
            cli.validate_credentials()
        
        assert exc_info.value.code == 1


class TestValidateStage:
    """Test stage validation method."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_validate_stage_exists(self, mock_boto_client):
        """Test validation succeeds when stage exists."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {
                    'Name': '/sales-agent/dev/item_table',
                    'Value': 'items-dev'
                }
            ]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        result = cli.validate_stage()
        
        assert result is True
        mock_ssm.get_parameters_by_path.assert_called_with(
            Path="/sales-agent/dev/",
            MaxResults=1
        )
    
    @patch('sales_agent_cli.boto3.client')
    def test_validate_stage_not_exists(self, mock_boto_client):
        """Test validation fails when stage doesn't exist."""
        mock_ssm = Mock()
        # First call returns empty (stage doesn't exist)
        # Second call returns available stages
        mock_ssm.get_parameters_by_path.side_effect = [
            {'Parameters': []},  # Stage validation
            {  # List available stages
                'Parameters': [
                    {'Name': '/sales-agent/dev/item_table'},
                    {'Name': '/sales-agent/prod/item_table'}
                ]
            }
        ]
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="nonexistent")
        
        with pytest.raises(SystemExit) as exc_info:
            cli.validate_stage()
        
        assert exc_info.value.code == 1
    
    @patch('sales_agent_cli.boto3.client')
    def test_validate_stage_client_error(self, mock_boto_client):
        """Test validation handles client errors."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetParametersByPath'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        
        with pytest.raises(SystemExit) as exc_info:
            cli.validate_stage()
        
        assert exc_info.value.code == 1


class TestListAvailableStages:
    """Test _list_available_stages helper method."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_available_stages(self, mock_boto_client):
        """Test listing available stages from Parameter Store."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {'Name': '/sales-agent/dev/item_table'},
                {'Name': '/sales-agent/dev/user_table'},
                {'Name': '/sales-agent/staging/item_table'},
                {'Name': '/sales-agent/prod/item_table'}
            ]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        stages = cli._list_available_stages()
        
        assert stages == ['dev', 'prod', 'staging']  # Sorted
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_available_stages_empty(self, mock_boto_client):
        """Test listing stages when none exist."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        stages = cli._list_available_stages()
        
        assert stages == []
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_available_stages_error(self, mock_boto_client):
        """Test listing stages handles errors gracefully."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.side_effect = Exception("Network error")
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="test")
        stages = cli._list_available_stages()
        
        assert stages == []  # Returns empty list on error
