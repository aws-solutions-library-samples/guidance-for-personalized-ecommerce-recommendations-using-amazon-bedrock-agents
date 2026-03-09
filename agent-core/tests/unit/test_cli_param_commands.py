"""
Unit tests for CLI parameter management commands.

Tests the param set, param get, and param list commands.

**Validates: Requirements 5.1, 5.2, 5.3, 13.7**
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from click.testing import CliRunner

# Import CLI components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../cli'))

from sales_agent_cli import cli, SalesAgentCLI


class TestParamSetCommand:
    """Test param set command."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_set_success(self, mock_boto_client):
        """Test successful parameter set operation."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/existing'}]
        }
        mock_ssm.put_parameter.return_value = {}
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'set',
            '--key', 'item_table',
            '--value', 'my-items-table'
        ])
        
        assert result.exit_code == 0
        assert '✓ Parameter set successfully' in result.output
        assert '/sales-agent/dev/item_table' in result.output
        assert 'my-items-table' in result.output
        
        # Verify put_parameter was called correctly
        mock_ssm.put_parameter.assert_called_once_with(
            Name='/sales-agent/dev/item_table',
            Value='my-items-table',
            Type='String',
            Overwrite=True,
            Description='Parameter for dev stage'
        )
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_set_overwrite_existing(self, mock_boto_client):
        """Test overwriting an existing parameter."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/prod/item_table'}]
        }
        mock_ssm.put_parameter.return_value = {}
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'prod',
            'param', 'set',
            '--key', 'item_table',
            '--value', 'new-value'
        ])
        
        assert result.exit_code == 0
        assert '✓ Parameter set successfully' in result.output
        
        # Verify Overwrite=True was used
        call_args = mock_ssm.put_parameter.call_args
        assert call_args[1]['Overwrite'] is True
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_set_access_denied(self, mock_boto_client):
        """Test param set with access denied error."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/existing'}]
        }
        mock_ssm.put_parameter.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'PutParameter'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'set',
            '--key', 'item_table',
            '--value', 'value'
        ])
        
        assert result.exit_code == 1
        assert 'Access denied' in result.output
        assert 'ssm:PutParameter' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_set_missing_key(self, mock_boto_client):
        """Test param set without required --key option."""
        mock_boto_client.return_value = Mock()
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'set',
            '--value', 'value'
        ])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_set_missing_value(self, mock_boto_client):
        """Test param set without required --value option."""
        mock_boto_client.return_value = Mock()
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'set',
            '--key', 'item_table'
        ])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()


class TestParamGetCommand:
    """Test param get command."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_get_success(self, mock_boto_client):
        """Test successful parameter get operation."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        mock_ssm.get_parameter.return_value = {
            'Parameter': {
                'Name': '/sales-agent/dev/item_table',
                'Value': 'my-items-table',
                'Type': 'String',
                'LastModifiedDate': '2024-01-01T00:00:00Z'
            }
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'get',
            '--key', 'item_table'
        ])
        
        assert result.exit_code == 0
        assert 'Parameter: item_table' in result.output
        assert '/sales-agent/dev/item_table' in result.output
        assert 'my-items-table' in result.output
        assert 'String' in result.output
        
        # Verify get_parameter was called correctly
        mock_ssm.get_parameter.assert_called_once_with(
            Name='/sales-agent/dev/item_table',
            WithDecryption=True
        )
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_get_not_found(self, mock_boto_client):
        """Test param get with parameter not found."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.side_effect = [
            {'Parameters': [{'Name': '/sales-agent/dev/existing'}]},  # Stage validation
            {'Parameters': [{'Name': '/sales-agent/dev/other_param'}]}  # Available params
        ]
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound', 'Message': 'Parameter not found'}},
            'GetParameter'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'get',
            '--key', 'nonexistent'
        ])
        
        assert result.exit_code == 1
        assert "Parameter 'nonexistent' not found" in result.output
        assert "stage 'dev'" in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_get_access_denied(self, mock_boto_client):
        """Test param get with access denied error."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetParameter'
        )
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'get',
            '--key', 'item_table'
        ])
        
        assert result.exit_code == 1
        assert 'Access denied' in result.output
        assert 'ssm:GetParameter' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_get_with_decryption(self, mock_boto_client):
        """Test param get uses WithDecryption for secure strings."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/secret'}]
        }
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
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'get',
            '--key', 'secret'
        ])
        
        assert result.exit_code == 0
        
        # Verify WithDecryption=True was used
        call_args = mock_ssm.get_parameter.call_args
        assert call_args[1]['WithDecryption'] is True


class TestParamListCommand:
    """Test param list command."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_list_success(self, mock_boto_client):
        """Test successful parameter list operation."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.side_effect = [
            # Stage validation
            {'Parameters': [{'Name': '/sales-agent/dev/item_table'}]},
            # List parameters
            {
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
                    },
                    {
                        'Name': '/sales-agent/dev/aoss_endpoint',
                        'Value': 'https://example.aoss.amazonaws.com',
                        'Type': 'String'
                    }
                ]
            }
        ]
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'list'
        ])
        
        assert result.exit_code == 0
        assert "Parameters for stage 'dev'" in result.output
        assert 'item_table' in result.output
        assert 'user_table' in result.output
        assert 'aoss_endpoint' in result.output
        assert 'my-items-table' in result.output
        assert 'Total: 3 parameter(s)' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_list_empty(self, mock_boto_client):
        """Test param list with no parameters."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.side_effect = [
            # Stage validation (has at least one param)
            {'Parameters': [{'Name': '/sales-agent/dev/temp'}]},
            # List parameters (empty)
            {'Parameters': []}
        ]
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'list'
        ])
        
        assert result.exit_code == 0
        assert "No parameters found for stage 'dev'" in result.output
        assert 'param set' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_list_truncates_long_values(self, mock_boto_client):
        """Test param list truncates long parameter values."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        
        long_value = 'a' * 100  # 100 character value
        
        mock_ssm.get_parameters_by_path.side_effect = [
            # Stage validation
            {'Parameters': [{'Name': '/sales-agent/dev/long_param'}]},
            # List parameters
            {
                'Parameters': [
                    {
                        'Name': '/sales-agent/dev/long_param',
                        'Value': long_value,
                        'Type': 'String'
                    }
                ]
            }
        ]
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'list'
        ])
        
        assert result.exit_code == 0
        assert '...' in result.output  # Value should be truncated
        assert long_value not in result.output  # Full value should not appear
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_list_access_denied(self, mock_boto_client):
        """Test param list with access denied error."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.side_effect = [
            # Stage validation
            {'Parameters': [{'Name': '/sales-agent/dev/item_table'}]},
            # List parameters - access denied
            ClientError(
                {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
                'GetParametersByPath'
            )
        ]
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'list'
        ])
        
        assert result.exit_code == 1
        assert 'Access denied' in result.output
        assert 'ssm:GetParametersByPath' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_param_list_sorted_output(self, mock_boto_client):
        """Test param list displays parameters in sorted order."""
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.side_effect = [
            # Stage validation
            {'Parameters': [{'Name': '/sales-agent/dev/item_table'}]},
            # List parameters (unsorted)
            {
                'Parameters': [
                    {'Name': '/sales-agent/dev/zebra', 'Value': 'z', 'Type': 'String'},
                    {'Name': '/sales-agent/dev/alpha', 'Value': 'a', 'Type': 'String'},
                    {'Name': '/sales-agent/dev/beta', 'Value': 'b', 'Type': 'String'}
                ]
            }
        ]
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'param', 'list'
        ])
        
        assert result.exit_code == 0
        
        # Check that alpha appears before beta, and beta before zebra
        alpha_pos = result.output.find('alpha')
        beta_pos = result.output.find('beta')
        zebra_pos = result.output.find('zebra')
        
        assert alpha_pos < beta_pos < zebra_pos


class TestListParametersHelper:
    """Test _list_parameters helper method."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_parameters_success(self, mock_boto_client):
        """Test _list_parameters returns parameter keys."""
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
        
        cli_instance = SalesAgentCLI(stage="dev")
        keys = cli_instance._list_parameters()
        
        assert keys == ['aoss_endpoint', 'item_table', 'user_table']  # Sorted
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_parameters_empty(self, mock_boto_client):
        """Test _list_parameters with no parameters."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli_instance = SalesAgentCLI(stage="dev")
        keys = cli_instance._list_parameters()
        
        assert keys == []
    
    @patch('sales_agent_cli.boto3.client')
    def test_list_parameters_error_handling(self, mock_boto_client):
        """Test _list_parameters handles errors gracefully."""
        mock_ssm = Mock()
        mock_ssm.get_parameters_by_path.side_effect = Exception("Network error")
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        cli_instance = SalesAgentCLI(stage="dev")
        keys = cli_instance._list_parameters()
        
        assert keys == []  # Returns empty list on error
