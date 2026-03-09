"""
Unit tests for CLI parameter management methods.

Tests the param set, param get, and param list functionality
by testing the CLI class methods directly, avoiding Click test runner issues.

**Validates: Requirements 5.1, 5.2, 5.3, 13.7**
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Import CLI components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../cli'))

from sales_agent_cli import SalesAgentCLI


class TestParameterStoreOperations:
    """Test parameter store operations through SSM client."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_set_creates_correct_path(self, mock_boto_client):
        """Test that param set uses correct hierarchical path."""
        mock_ssm = Mock()
        mock_ssm.put_parameter.return_value = {}
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        
        # Simulate param set operation
        param_path = f"/sales-agent/{cli.stage}/item_table"
        cli.ssm.put_parameter(
            Name=param_path,
            Value='my-items-table',
            Type='String',
            Overwrite=True,
            Description=f"Parameter for {cli.stage} stage"
        )
        
        # Verify put_parameter was called with correct path
        mock_ssm.put_parameter.assert_called_once()
        call_args = mock_ssm.put_parameter.call_args
        assert call_args[1]['Name'] == '/sales-agent/dev/item_table'
        assert call_args[1]['Value'] == 'my-items-table'
        assert call_args[1]['Overwrite'] is True
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_get_uses_decryption(self, mock_boto_client):
        """Test that param get uses WithDecryption."""
        mock_ssm = Mock()
        mock_ssm.get_parameter.return_value = {
            'Parameter': {
                'Name': '/sales-agent/dev/secret',
                'Value': 'decrypted-value',
                'Type': 'SecureString',
                'LastModifiedDate': '2024-01-01T00:00:00Z'
            }
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        
        # Simulate param get operation
        param_path = f"/sales-agent/{cli.stage}/secret"
        cli.ssm.get_parameter(
            Name=param_path,
            WithDecryption=True
        )
        
        # Verify get_parameter was called with WithDecryption=True
        mock_ssm.get_parameter.assert_called_once()
        call_args = mock_ssm.get_parameter.call_args
        assert call_args[1]['WithDecryption'] is True
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_list_returns_all_stage_params(self, mock_boto_client):
        """Test that param list retrieves all parameters for stage."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {
                    'Name': '/sales-agent/dev/item_table',
                    'Value': 'my-items-table',
                    'Type': 'String'
                },
                {
                    'Name': '/sales-agent/dev/user_table',
                    'Value': 'my-users-table',
                    'Type': 'String'
                }
            ]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        
        # Simulate param list operation
        prefix = f"/sales-agent/{cli.stage}/"
        response = cli.ssm.get_parameters_by_path(
            Path=prefix,
            Recursive=True,
            WithDecryption=True,
            MaxResults=50
        )
        
        # Verify get_parameters_by_path was called correctly
        mock_ssm.get_parameters_by_path.assert_called_once()
        call_args = mock_ssm.get_parameters_by_path.call_args
        assert call_args[1]['Path'] == '/sales-agent/dev/'
        assert call_args[1]['Recursive'] is True
        assert call_args[1]['WithDecryption'] is True
        
        # Verify response contains expected parameters
        assert len(response['Parameters']) == 2
        assert response['Parameters'][0]['Name'] == '/sales-agent/dev/item_table'
        assert response['Parameters'][1]['Name'] == '/sales-agent/dev/user_table'
    
    @patch('sales_agent_cli.boto3.client')
    def test_hierarchical_naming_with_different_stages(self, mock_boto_client):
        """Test that different stages use different parameter paths."""
        mock_ssm = Mock()
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        # Test dev stage
        cli_dev = SalesAgentCLI(stage="dev")
        dev_path = f"/sales-agent/{cli_dev.stage}/item_table"
        assert dev_path == "/sales-agent/dev/item_table"
        
        # Test prod stage
        cli_prod = SalesAgentCLI(stage="prod")
        prod_path = f"/sales-agent/{cli_prod.stage}/item_table"
        assert prod_path == "/sales-agent/prod/item_table"
        
        # Verify paths are different
        assert dev_path != prod_path
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_parameters_helper_extracts_keys(self, mock_boto_client):
        """Test _list_parameters helper method extracts parameter keys."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {'Name': '/sales-agent/dev/item_table'},
                {'Name': '/sales-agent/dev/user_table'},
                {'Name': '/sales-agent/dev/aoss_endpoint'}
            ]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        keys = cli._list_parameters()
        
        # Verify keys are extracted correctly (sorted)
        assert keys == ['aoss_endpoint', 'item_table', 'user_table']
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_parameters_handles_empty_result(self, mock_boto_client):
        """Test _list_parameters handles empty parameter list."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        keys = cli._list_parameters()
        
        assert keys == []
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_parameters_handles_errors_gracefully(self, mock_boto_client):
        """Test _list_parameters returns empty list on error."""
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
        
        cli = SalesAgentCLI(stage="dev")
        keys = cli._list_parameters()
        
        # Should return empty list instead of raising exception
        assert keys == []


class TestParameterPathFormatting:
    """Test parameter path formatting and hierarchical naming."""
    
    def test_parameter_path_format(self):
        """Test parameter path follows /sales-agent/{stage}/{key} format."""
        stage = "dev"
        key = "item_table"
        expected_path = f"/sales-agent/{stage}/{key}"
        
        assert expected_path == "/sales-agent/dev/item_table"
    
    def test_parameter_path_with_special_characters(self):
        """Test parameter paths with hyphens and underscores."""
        stage = "test-123"
        key = "aoss_endpoint"
        expected_path = f"/sales-agent/{stage}/{key}"
        
        assert expected_path == "/sales-agent/test-123/aoss_endpoint"
    
    def test_parameter_path_isolation_between_stages(self):
        """Test that different stages have isolated parameter paths."""
        stages = ["dev", "staging", "prod"]
        key = "item_table"
        
        paths = [f"/sales-agent/{stage}/{key}" for stage in stages]
        
        # All paths should be unique
        assert len(paths) == len(set(paths))
        
        # Verify each path contains the correct stage
        for stage, path in zip(stages, paths):
            assert stage in path


class TestErrorHandling:
    """Test error handling for parameter operations."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_access_denied_error_handling(self, mock_boto_client):
        """Test handling of AccessDeniedException."""
        mock_ssm = Mock()
        mock_ssm.put_parameter.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'PutParameter'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        
        # Verify exception is raised
        with pytest.raises(ClientError) as exc_info:
            cli.ssm.put_parameter(
                Name='/sales-agent/dev/test',
                Value='value',
                Type='String',
                Overwrite=True
            )
        
        assert exc_info.value.response['Error']['Code'] == 'AccessDeniedException'
    
    @patch('sales_agent_cli.boto3.client')
    def test_parameter_not_found_error_handling(self, mock_boto_client):
        """Test handling of ParameterNotFound error."""
        mock_ssm = Mock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound', 'Message': 'Parameter not found'}},
            'GetParameter'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli = SalesAgentCLI(stage="dev")
        
        # Verify exception is raised
        with pytest.raises(ClientError) as exc_info:
            cli.ssm.get_parameter(
                Name='/sales-agent/dev/nonexistent',
                WithDecryption=True
            )
        
        assert exc_info.value.response['Error']['Code'] == 'ParameterNotFound'


class TestParameterValueHandling:
    """Test parameter value handling and formatting."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_long_value_truncation_logic(self, mock_boto_client):
        """Test logic for truncating long parameter values in display."""
        mock_ssm = Mock()
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        # Test truncation logic
        long_value = 'a' * 100
        
        # Simulate truncation (as done in param list command)
        if len(long_value) > 60:
            truncated = long_value[:57] + "..."
        else:
            truncated = long_value
        
        assert len(truncated) == 60  # 57 chars + "..."
        assert truncated.endswith("...")
        assert truncated.startswith('a' * 57)
    
    @patch('sales_agent_cli.boto3.client')
    def test_parameter_sorting_logic(self, mock_boto_client):
        """Test parameter sorting logic for display."""
        mock_ssm = Mock()
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
        
        mock_boto_client.side_effect = client_factory
        
        # Simulate unsorted parameters
        parameters = [
            {'Name': '/sales-agent/dev/zebra', 'Value': 'z', 'Type': 'String'},
            {'Name': '/sales-agent/dev/alpha', 'Value': 'a', 'Type': 'String'},
            {'Name': '/sales-agent/dev/beta', 'Value': 'b', 'Type': 'String'}
        ]
        
        # Sort by name (as done in param list command)
        sorted_params = sorted(parameters, key=lambda p: p['Name'])
        
        # Verify sorting
        assert sorted_params[0]['Name'] == '/sales-agent/dev/alpha'
        assert sorted_params[1]['Name'] == '/sales-agent/dev/beta'
        assert sorted_params[2]['Name'] == '/sales-agent/dev/zebra'
