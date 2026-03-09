"""
Unit tests for CLI logs command.

Tests the logs command functionality including:
- Log retrieval with tail option
- Time range filtering
- Log formatting
- Error handling

Requirements: 5.7, 5.8, 10.8
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# Import CLI module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../cli'))

from sales_agent_cli import _parse_time_range, _format_log_event, _query_cloudwatch_logs, _get_log_group_name


class TestParseTimeRange:
    """Test suite for _parse_time_range function."""
    
    def test_parse_iso_format(self):
        """Test parsing ISO format timestamps."""
        start = '2024-01-01 10:00'
        end = '2024-01-01 11:00'
        
        start_ms, end_ms = _parse_time_range(start, end)
        
        assert start_ms is not None
        assert end_ms is not None
        assert end_ms > start_ms
    
    def test_parse_relative_time_hours(self):
        """Test parsing relative time in hours."""
        start = '1h ago'
        
        start_ms, end_ms = _parse_time_range(start, None)
        
        assert start_ms is not None
        assert end_ms is None
        
        # Verify it's approximately 1 hour ago
        now_ms = int(datetime.now().timestamp() * 1000)
        hour_ms = 60 * 60 * 1000
        assert abs(now_ms - start_ms - hour_ms) < 1000  # Within 1 second tolerance
    
    def test_parse_relative_time_minutes(self):
        """Test parsing relative time in minutes."""
        start = '30m ago'
        
        start_ms, end_ms = _parse_time_range(start, None)
        
        assert start_ms is not None
        
        # Verify it's approximately 30 minutes ago
        now_ms = int(datetime.now().timestamp() * 1000)
        minutes_ms = 30 * 60 * 1000
        assert abs(now_ms - start_ms - minutes_ms) < 1000
    
    def test_parse_relative_time_days(self):
        """Test parsing relative time in days."""
        start = '2d ago'
        
        start_ms, end_ms = _parse_time_range(start, None)
        
        assert start_ms is not None
        
        # Verify it's approximately 2 days ago
        now_ms = int(datetime.now().timestamp() * 1000)
        days_ms = 2 * 24 * 60 * 60 * 1000
        assert abs(now_ms - start_ms - days_ms) < 1000
    
    def test_parse_invalid_format(self):
        """Test parsing invalid time format."""
        with pytest.raises(ValueError):
            _parse_time_range('invalid-time', None)
    
    def test_parse_none_values(self):
        """Test parsing with None values."""
        start_ms, end_ms = _parse_time_range(None, None)
        
        assert start_ms is None
        assert end_ms is None


class TestFormatLogEvent:
    """Test suite for _format_log_event function."""
    
    def test_format_plain_text_log(self):
        """Test formatting plain text log event."""
        event = {
            'timestamp': int(datetime.now().timestamp() * 1000),
            'message': 'This is a plain text log message'
        }
        
        formatted = _format_log_event(event)
        
        assert 'This is a plain text log message' in formatted
        assert '[' in formatted  # Timestamp bracket
    
    def test_format_json_log(self):
        """Test formatting JSON structured log event."""
        event = {
            'timestamp': int(datetime.now().timestamp() * 1000),
            'message': '{"level": "INFO", "message": "Structured log message", "user_id": "123"}'
        }
        
        formatted = _format_log_event(event)
        
        assert 'Structured log message' in formatted
        assert 'INFO' in formatted
    
    def test_format_error_log(self):
        """Test formatting error level log."""
        event = {
            'timestamp': int(datetime.now().timestamp() * 1000),
            'message': '{"level": "ERROR", "message": "An error occurred"}'
        }
        
        formatted = _format_log_event(event)
        
        assert 'An error occurred' in formatted
        assert 'ERROR' in formatted
    
    def test_format_log_with_timestamp(self):
        """Test that formatted log includes readable timestamp."""
        timestamp = datetime(2024, 1, 1, 10, 30, 45, 123000)
        event = {
            'timestamp': int(timestamp.timestamp() * 1000),
            'message': 'Test message'
        }
        
        formatted = _format_log_event(event)
        
        assert '2024-01-01' in formatted
        assert '10:30:45' in formatted


class TestQueryCloudWatchLogs:
    """Test suite for _query_cloudwatch_logs function."""
    
    def test_query_with_tail(self):
        """Test querying logs with tail limit."""
        mock_logs = Mock()
        mock_logs.filter_log_events.return_value = {
            'events': [
                {'timestamp': 1000, 'message': 'Log 1'},
                {'timestamp': 2000, 'message': 'Log 2'},
                {'timestamp': 3000, 'message': 'Log 3'}
            ]
        }
        
        events = _query_cloudwatch_logs(
            mock_logs,
            '/aws/sales-agent/dev',
            None,
            None,
            tail=2
        )
        
        # Should return only last 2 events
        assert len(events) == 2
        assert events[0]['message'] == 'Log 2'
        assert events[1]['message'] == 'Log 3'
    
    def test_query_with_time_range(self):
        """Test querying logs with time range."""
        mock_logs = Mock()
        mock_logs.filter_log_events.return_value = {
            'events': [
                {'timestamp': 1000, 'message': 'Log 1'}
            ]
        }
        
        start_time = 1000
        end_time = 2000
        
        events = _query_cloudwatch_logs(
            mock_logs,
            '/aws/sales-agent/dev',
            start_time,
            end_time,
            None
        )
        
        # Verify API call
        mock_logs.filter_log_events.assert_called_once()
        call_args = mock_logs.filter_log_events.call_args[1]
        assert call_args['startTime'] == start_time
        assert call_args['endTime'] == end_time
    
    def test_query_resource_not_found(self):
        """Test querying non-existent log group."""
        mock_logs = Mock()
        mock_logs.filter_log_events.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not found'}},
            'FilterLogEvents'
        )
        
        with pytest.raises(Exception) as exc_info:
            _query_cloudwatch_logs(
                mock_logs,
                '/aws/sales-agent/dev',
                None,
                None,
                None
            )
        
        assert 'not found' in str(exc_info.value).lower()
    
    def test_query_access_denied(self):
        """Test querying with insufficient permissions."""
        mock_logs = Mock()
        mock_logs.filter_log_events.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'FilterLogEvents'
        )
        
        with pytest.raises(Exception) as exc_info:
            _query_cloudwatch_logs(
                mock_logs,
                '/aws/sales-agent/dev',
                None,
                None,
                None
            )
        
        assert 'Access denied' in str(exc_info.value)


class TestGetLogGroupName:
    """Test suite for _get_log_group_name function."""
    
    def test_get_log_group_from_stack_output(self):
        """Test getting log group name from CloudFormation stack outputs."""
        with patch('sales_agent_cli.boto3.client') as mock_client:
            mock_cfn = Mock()
            mock_client.return_value = mock_cfn
            
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [
                    {
                        'Outputs': [
                            {
                                'OutputKey': 'LogGroupName',
                                'OutputValue': '/aws/sales-agent/dev'
                            }
                        ]
                    }
                ]
            }
            
            log_group = _get_log_group_name('dev')
            
            assert log_group == '/aws/sales-agent/dev'
    
    def test_get_log_group_fallback_to_default(self):
        """Test fallback to default pattern when stack not found."""
        with patch('sales_agent_cli.boto3.client') as mock_client:
            mock_cfn = Mock()
            mock_client.return_value = mock_cfn
            
            mock_cfn.describe_stacks.side_effect = ClientError(
                {'Error': {'Code': 'ValidationError', 'Message': 'Stack not found'}},
                'DescribeStacks'
            )
            
            log_group = _get_log_group_name('dev')
            
            # Should return default pattern
            assert log_group == '/aws/sales-agent/dev'
    
    def test_get_log_group_no_output(self):
        """Test when stack exists but has no LogGroupName output."""
        with patch('sales_agent_cli.boto3.client') as mock_client:
            mock_cfn = Mock()
            mock_client.return_value = mock_cfn
            
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [
                    {
                        'Outputs': []
                    }
                ]
            }
            
            log_group = _get_log_group_name('dev')
            
            # Should return default pattern
            assert log_group == '/aws/sales-agent/dev'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
