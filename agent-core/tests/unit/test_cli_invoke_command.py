"""
Unit tests for CLI invoke command.

Tests the invoke command for runtime invocation with streaming responses.

**Validates: Requirements 5.4, 5.5, 5.6, 13.7**
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from click.testing import CliRunner
import json

# Import CLI components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../cli'))

from sales_agent_cli import cli, _get_runtime_endpoint, _invoke_runtime, _display_event


class TestInvokeCommand:
    """Test invoke command."""
    
    @patch('sales_agent_cli.requests.post')
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_success(self, mock_boto_client, mock_get_endpoint, mock_post):
        """Test successful runtime invocation."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        # Mock runtime endpoint
        mock_get_endpoint.return_value = 'http://example-alb.us-east-1.elb.amazonaws.com'
        
        # Mock HTTP response with streaming events
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            json.dumps({'type': 'text', 'content': 'Hello'}).encode('utf-8'),
            json.dumps({'type': 'text', 'content': ' world'}).encode('utf-8'),
            json.dumps({'type': 'done'}).encode('utf-8')
        ]
        mock_post.return_value = mock_response
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Find me a blue dress'
        ])
        
        assert result.exit_code == 0
        assert 'Invoking runtime' in result.output
        assert 'Find me a blue dress' in result.output
        assert 'Agent Response' in result.output
        assert '✓ Invocation complete' in result.output
        
        # Verify HTTP POST was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'http://example-alb.us-east-1.elb.amazonaws.com/invoke'
        assert call_args[1]['json']['prompt'] == 'Find me a blue dress'
        assert call_args[1]['stream'] is True
        assert call_args[1]['timeout'] == 60
    
    @patch('sales_agent_cli.requests.post')
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_with_session_id(self, mock_boto_client, mock_get_endpoint, mock_post):
        """Test invoke with session ID parameter."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        mock_get_endpoint.return_value = 'http://example-alb.us-east-1.elb.amazonaws.com'
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            json.dumps({'type': 'done'}).encode('utf-8')
        ]
        mock_post.return_value = mock_response
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Continue shopping',
            '--session-id', 's-20240101120000'
        ])
        
        assert result.exit_code == 0
        assert 'Session ID: s-20240101120000' in result.output
        
        # Verify session_id was included in payload
        call_args = mock_post.call_args
        assert call_args[1]['json']['session_id'] == 's-20240101120000'
    
    @patch('sales_agent_cli.requests.post')
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_with_actor_id(self, mock_boto_client, mock_get_endpoint, mock_post):
        """Test invoke with actor ID parameter."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        mock_get_endpoint.return_value = 'http://example-alb.us-east-1.elb.amazonaws.com'
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            json.dumps({'type': 'done'}).encode('utf-8')
        ]
        mock_post.return_value = mock_response
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Show recommendations',
            '--actor-id', 'user-123'
        ])
        
        assert result.exit_code == 0
        assert 'Actor ID: user-123' in result.output
        
        # Verify actor_id was included in payload
        call_args = mock_post.call_args
        assert call_args[1]['json']['actor_id'] == 'user-123'
    
    @patch('sales_agent_cli.requests.post')
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_with_both_ids(self, mock_boto_client, mock_get_endpoint, mock_post):
        """Test invoke with both session ID and actor ID."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        mock_get_endpoint.return_value = 'http://example-alb.us-east-1.elb.amazonaws.com'
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            json.dumps({'type': 'done'}).encode('utf-8')
        ]
        mock_post.return_value = mock_response
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Test message',
            '--session-id', 's-123',
            '--actor-id', 'user-456'
        ])
        
        assert result.exit_code == 0
        assert 'Session ID: s-123' in result.output
        assert 'Actor ID: user-456' in result.output
        
        # Verify both IDs were included in payload
        call_args = mock_post.call_args
        assert call_args[1]['json']['session_id'] == 's-123'
        assert call_args[1]['json']['actor_id'] == 'user-456'
    
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_endpoint_not_found(self, mock_boto_client, mock_get_endpoint):
        """Test invoke when runtime endpoint is not found."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        mock_get_endpoint.return_value = None
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Test'
        ])
        
        assert result.exit_code == 1
        assert 'Runtime endpoint not found' in result.output
        assert 'Troubleshooting steps' in result.output
        assert 'describe-stacks' in result.output
    
    @patch('sales_agent_cli.requests.post')
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_connection_error(self, mock_boto_client, mock_get_endpoint, mock_post):
        """Test invoke with connection error."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        mock_get_endpoint.return_value = 'http://example-alb.us-east-1.elb.amazonaws.com'
        
        # Simulate connection error
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Test'
        ])
        
        assert result.exit_code == 1
        assert 'Failed to invoke runtime' in result.output
        assert 'Connection failed' in result.output
        assert 'Troubleshooting steps' in result.output
    
    @patch('sales_agent_cli.requests.post')
    @patch('sales_agent_cli._get_runtime_endpoint')
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_http_error(self, mock_boto_client, mock_get_endpoint, mock_post):
        """Test invoke with HTTP error response."""
        # Setup mocks
        mock_ssm = Mock()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [{'Name': '/sales-agent/dev/item_table'}]
        }
        
        def client_factory(service_name):
            if service_name == 'ssm':
                return mock_ssm
            elif service_name == 'sts':
                return mock_sts
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        mock_get_endpoint.return_value = 'http://example-alb.us-east-1.elb.amazonaws.com'
        
        # Simulate HTTP 500 error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke',
            '--message', 'Test'
        ])
        
        assert result.exit_code == 1
        assert 'Failed to invoke runtime' in result.output
        assert 'HTTP 500' in result.output
    
    @patch('sales_agent_cli.boto3.client')
    def test_invoke_missing_message(self, mock_boto_client):
        """Test invoke without required --message option."""
        mock_boto_client.return_value = Mock()
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--stage', 'dev',
            'invoke'
        ])
        
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()


class TestGetRuntimeEndpoint:
    """Test _get_runtime_endpoint helper function."""
    
    @patch('sales_agent_cli.boto3.client')
    def test_get_endpoint_success(self, mock_boto_client):
        """Test successful endpoint retrieval."""
        mock_cfn = Mock()
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {
                        'OutputKey': 'RuntimeEndpoint',
                        'OutputValue': 'http://example-alb.us-east-1.elb.amazonaws.com'
                    }
                ]
            }]
        }
        mock_boto_client.return_value = mock_cfn
        
        endpoint = _get_runtime_endpoint('dev')
        
        assert endpoint == 'http://example-alb.us-east-1.elb.amazonaws.com'
        mock_cfn.describe_stacks.assert_called_once_with(
            StackName='SalesAgentRuntimeStack-dev'
        )
    
    @patch('sales_agent_cli.boto3.client')
    def test_get_endpoint_stack_not_found(self, mock_boto_client):
        """Test endpoint retrieval when stack doesn't exist."""
        mock_cfn = Mock()
        mock_cfn.describe_stacks.side_effect = ClientError(
            {'Error': {'Code': 'ValidationError', 'Message': 'Stack does not exist'}},
            'DescribeStacks'
        )
        mock_boto_client.return_value = mock_cfn
        
        endpoint = _get_runtime_endpoint('nonexistent')
        
        assert endpoint is None
    
    @patch('sales_agent_cli.boto3.client')
    def test_get_endpoint_no_outputs(self, mock_boto_client):
        """Test endpoint retrieval when stack has no outputs."""
        mock_cfn = Mock()
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': []
            }]
        }
        mock_boto_client.return_value = mock_cfn
        
        endpoint = _get_runtime_endpoint('dev')
        
        assert endpoint is None
    
    @patch('sales_agent_cli.boto3.client')
    def test_get_endpoint_missing_runtime_output(self, mock_boto_client):
        """Test endpoint retrieval when RuntimeEndpoint output is missing."""
        mock_cfn = Mock()
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {
                        'OutputKey': 'VpcId',
                        'OutputValue': 'vpc-12345'
                    }
                ]
            }]
        }
        mock_boto_client.return_value = mock_cfn
        
        endpoint = _get_runtime_endpoint('dev')
        
        assert endpoint is None


class TestDisplayEvent:
    """Test _display_event helper function."""
    
    def test_display_text_event(self, capsys):
        """Test displaying text event."""
        event = {'type': 'text', 'content': 'Hello world'}
        _display_event(event)
        
        captured = capsys.readouterr()
        assert 'Hello world' in captured.out
    
    def test_display_tool_call_event(self, capsys):
        """Test displaying tool call event."""
        event = {'type': 'tool_call', 'tool_name': 'search_product'}
        _display_event(event)
        
        captured = capsys.readouterr()
        assert 'Calling tool: search_product' in captured.out
    
    def test_display_tool_result_event(self, capsys):
        """Test displaying tool result event."""
        event = {'type': 'tool_result', 'tool_name': 'search_product'}
        _display_event(event)
        
        captured = capsys.readouterr()
        assert 'Tool search_product completed' in captured.out
    
    def test_display_error_event(self, capsys):
        """Test displaying error event."""
        event = {'type': 'error', 'error': 'Something went wrong'}
        _display_event(event)
        
        captured = capsys.readouterr()
        assert 'Error: Something went wrong' in captured.out
    
    def test_display_done_event(self, capsys):
        """Test displaying done event."""
        event = {'type': 'done'}
        _display_event(event)
        
        captured = capsys.readouterr()
        # Done event just prints a newline
        assert captured.out == '\n'
    
    def test_display_unknown_event(self, capsys):
        """Test displaying unknown event type."""
        event = {'type': 'unknown_type', 'data': 'some data'}
        _display_event(event)
        
        # Should not crash, just log debug message
        captured = capsys.readouterr()
        # Unknown events are logged but not displayed to user
        assert captured.out == ''


class TestInvokeRuntime:
    """Test _invoke_runtime helper function."""
    
    @patch('sales_agent_cli.requests.post')
    def test_invoke_runtime_success(self, mock_post):
        """Test successful runtime invocation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            json.dumps({'type': 'text', 'content': 'Response'}).encode('utf-8'),
            json.dumps({'type': 'done'}).encode('utf-8')
        ]
        mock_post.return_value = mock_response
        
        payload = {'prompt': 'Test message'}
        
        # Should not raise exception
        _invoke_runtime('http://example.com', payload)
        
        mock_post.assert_called_once_with(
            'http://example.com/invoke',
            json=payload,
            stream=True,
            timeout=60,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        )
    
    @patch('sales_agent_cli.requests.post')
    def test_invoke_runtime_connection_error(self, mock_post):
        """Test runtime invocation with connection error."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        payload = {'prompt': 'Test'}
        
        with pytest.raises(Exception) as exc_info:
            _invoke_runtime('http://example.com', payload)
        
        assert 'Connection failed' in str(exc_info.value)
    
    @patch('sales_agent_cli.requests.post')
    def test_invoke_runtime_timeout(self, mock_post):
        """Test runtime invocation with timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        payload = {'prompt': 'Test'}
        
        with pytest.raises(Exception) as exc_info:
            _invoke_runtime('http://example.com', payload)
        
        assert 'timed out' in str(exc_info.value)
    
    @patch('sales_agent_cli.requests.post')
    def test_invoke_runtime_http_error(self, mock_post):
        """Test runtime invocation with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        
        payload = {'prompt': 'Test'}
        
        with pytest.raises(Exception) as exc_info:
            _invoke_runtime('http://example.com', payload)
        
        assert 'HTTP 500' in str(exc_info.value)
