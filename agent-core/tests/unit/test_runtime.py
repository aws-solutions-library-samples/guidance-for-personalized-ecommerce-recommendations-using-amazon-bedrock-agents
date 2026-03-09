"""
Unit tests for runtime application.

Tests configuration loading, native tools (search_product, get_recommendation),
error handling for missing parameters, and AWS service failures.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError


class TestConfigurationLoading:
    """Test configuration loading from Parameter Store."""
    
    @patch('runtime.strands_agent.boto3.client')
    @patch.dict('os.environ', {'STAGE': 'test'})
    def test_load_config_success(self, mock_boto_client):
        """Test successful configuration loading from Parameter Store."""
        # Import after patching
        from runtime.strands_agent import load_config
        
        # Mock SSM client
        mock_ssm = Mock()
        mock_boto_client.return_value = mock_ssm
        
        # Mock parameter response
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {'Name': '/sales-agent/test/item_table', 'Value': 'items-test'},
                {'Name': '/sales-agent/test/user_table', 'Value': 'users-test'},
                {'Name': '/sales-agent/test/aoss_endpoint', 'Value': 'https://aoss.test'},
                {'Name': '/sales-agent/test/recommender_arn', 'Value': 'arn:aws:personalize:test'},
                {'Name': '/sales-agent/test/s3_bucket', 'Value': 'bucket-test'},
                {'Name': '/sales-agent/test/memory_id', 'Value': 'mem-123'},
            ]
        }
        
        # Load configuration
        config = load_config('test')
        
        # Verify configuration
        assert config['item_table'] == 'items-test'
        assert config['user_table'] == 'users-test'
        assert config['aoss_endpoint'] == 'https://aoss.test'
        assert config['recommender_arn'] == 'arn:aws:personalize:test'
        assert config['s3_bucket'] == 'bucket-test'
        assert config['memory_id'] == 'mem-123'
        
        # Verify SSM was called correctly
        mock_ssm.get_parameters_by_path.assert_called_once_with(
            Path='/sales-agent/test/',
            Recursive=True,
            WithDecryption=True
        )
    
    @patch('runtime.strands_agent.boto3.client')
    @patch.dict('os.environ', {'STAGE': 'test'})
    def test_load_config_missing_stage(self, mock_boto_client):
        """Test that missing STAGE environment variable causes exit."""
        from runtime.strands_agent import load_config
        
        # Call without stage parameter and no STAGE env var
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                load_config()
            
            assert exc_info.value.code == 1
    
    @patch('runtime.strands_agent.boto3.client')
    @patch.dict('os.environ', {'STAGE': 'test'})
    def test_load_config_no_parameters_found(self, mock_boto_client):
        """Test that missing parameters cause exit with error."""
        from runtime.strands_agent import load_config
        
        # Mock SSM client with empty response
        mock_ssm = Mock()
        mock_boto_client.return_value = mock_ssm
        mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
        
        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            load_config('test')
        
        assert exc_info.value.code == 1
    
    @patch('runtime.strands_agent.boto3.client')
    @patch.dict('os.environ', {'STAGE': 'test'})
    def test_load_config_missing_required_parameters(self, mock_boto_client):
        """Test that missing required parameters cause exit."""
        from runtime.strands_agent import load_config
        
        # Mock SSM client with incomplete parameters
        mock_ssm = Mock()
        mock_boto_client.return_value = mock_ssm
        mock_ssm.get_parameters_by_path.return_value = {
            'Parameters': [
                {'Name': '/sales-agent/test/item_table', 'Value': 'items-test'},
                {'Name': '/sales-agent/test/user_table', 'Value': 'users-test'},
                # Missing: aoss_endpoint, recommender_arn, memory_id
            ]
        }
        
        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            load_config('test')
        
        assert exc_info.value.code == 1
    
    @patch('runtime.strands_agent.boto3.client')
    @patch.dict('os.environ', {'STAGE': 'test'})
    def test_load_config_ssm_client_error(self, mock_boto_client):
        """Test that SSM client errors cause exit."""
        from runtime.strands_agent import load_config
        
        # Mock SSM client that raises exception
        mock_ssm = Mock()
        mock_boto_client.return_value = mock_ssm
        mock_ssm.get_parameters_by_path.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetParametersByPath'
        )
        
        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            load_config('test')
        
        assert exc_info.value.code == 1


class TestSearchProductTool:
    """Test search_product native tool."""
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._aoss_client')
    def test_search_product_success(self, mock_aoss, mock_bedrock):
        """Test successful product search."""
        from runtime.strands_agent import search_product
        
        # Mock Bedrock embedding response
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode('utf-8'))
        }
        
        # Mock OpenSearch response
        mock_aoss.search.return_value = {
            'hits': {
                'hits': [
                    {
                        '_source': {
                            'item_id': 'item-123',
                            'price': '29.99',
                            'style': 'casual',
                            'image_product_description': 'Blue cotton t-shirt with modern design'
                        }
                    },
                    {
                        '_source': {
                            'item_id': 'item-456',
                            'price': '39.99',
                            'style': 'formal',
                            'image_product_description': 'Black dress shirt with button-down collar'
                        }
                    }
                ]
            }
        }
        
        # Call search_product
        result = search_product("blue shirt")
        
        # Verify result
        result_data = json.loads(result)
        assert len(result_data) == 2
        assert result_data[0]['item_id'] == 'item-123'
        assert result_data[0]['price'] == '29.99'
        assert result_data[0]['style'] == 'casual'
        assert 'Blue cotton t-shirt' in result_data[0]['desc']
        
        # Verify Bedrock was called
        mock_bedrock.invoke_model.assert_called_once()
        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        assert call_kwargs['modelId'] == 'amazon.titan-embed-image-v1'
        
        # Verify OpenSearch was called
        mock_aoss.search.assert_called_once()
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._aoss_client')
    def test_search_product_no_results(self, mock_aoss, mock_bedrock):
        """Test product search with no results."""
        from runtime.strands_agent import search_product
        
        # Mock Bedrock embedding response
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode('utf-8'))
        }
        
        # Mock OpenSearch response with no hits
        mock_aoss.search.return_value = {
            'hits': {'hits': []}
        }
        
        # Call search_product
        result = search_product("nonexistent product")
        
        # Verify empty result
        result_data = json.loads(result)
        assert len(result_data) == 0
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._aoss_client')
    def test_search_product_bedrock_error(self, mock_aoss, mock_bedrock):
        """Test search_product handles Bedrock errors."""
        from runtime.strands_agent import search_product
        
        # Mock Bedrock error
        mock_bedrock.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'InvokeModel'
        )
        
        # Call search_product
        result = search_product("blue shirt")
        
        # Verify error response
        result_data = json.loads(result)
        assert 'error' in result_data
        assert 'ThrottlingException' in result_data['error'] or 'Rate exceeded' in result_data['error']
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._aoss_client')
    def test_search_product_opensearch_error(self, mock_aoss, mock_bedrock):
        """Test search_product handles OpenSearch errors."""
        from runtime.strands_agent import search_product
        
        # Mock Bedrock success
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode('utf-8'))
        }
        
        # Mock OpenSearch error
        mock_aoss.search.side_effect = Exception("Connection timeout")
        
        # Call search_product
        result = search_product("blue shirt")
        
        # Verify error response
        result_data = json.loads(result)
        assert 'error' in result_data
        assert 'Connection timeout' in result_data['error']


class TestGetRecommendationTool:
    """Test get_recommendation native tool."""
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._personalize_rt')
    @patch('runtime.strands_agent._get_user_info')
    @patch('runtime.strands_agent._get_item_info')
    def test_get_recommendation_success(self, mock_get_item, mock_get_user, mock_personalize, mock_bedrock):
        """Test successful recommendation generation."""
        from runtime.strands_agent import get_recommendation
        
        # Mock user info
        mock_get_user.return_value = {
            'user_id': '123',
            'age': '25',
            'gender': 'F',
            'visited': ['item-1', 'item-2'],
            'add_to_cart': ['item-3'],
            'purchased': ['item-4']
        }
        
        # Mock item info
        mock_get_item.return_value = {
            'item_id': 'item-1',
            'title': 'Blue Dress',
            'price': '49.99',
            'style': 'casual'
        }
        
        # Mock Personalize response
        mock_personalize.get_recommendations.return_value = {
            'itemList': [
                {'itemId': 'item-100'},
                {'itemId': 'item-101'},
                {'itemId': 'item-102'}
            ]
        }
        
        # Mock Bedrock LLM response
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'content': [{'text': 'Based on your history, I recommend these items.'}]
            }).encode('utf-8'))
        }
        
        # Call get_recommendation
        result = get_recommendation("123", "casual dresses")
        
        # Verify result
        result_data = json.loads(result)
        assert 'items' in result_data
        assert 'summarize' in result_data
        assert len(result_data['items']) == 3
        assert result_data['items'][0]['itemId'] == 'item-100'
        assert 'recommend' in result_data['summarize'].lower()
        
        # Verify Personalize was called
        mock_personalize.get_recommendations.assert_called_once()
        
        # Verify Bedrock was called for summary
        mock_bedrock.invoke_model.assert_called_once()
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._personalize_rt')
    @patch('runtime.strands_agent._get_user_info')
    def test_get_recommendation_no_items(self, mock_get_user, mock_personalize, mock_bedrock):
        """Test recommendation with no items returned."""
        from runtime.strands_agent import get_recommendation
        
        # Mock user info
        mock_get_user.return_value = {
            'user_id': '123',
            'age': '25',
            'gender': 'F',
            'visited': [],
            'add_to_cart': [],
            'purchased': []
        }
        
        # Mock Personalize response with no items
        mock_personalize.get_recommendations.return_value = {
            'itemList': []
        }
        
        # Mock Bedrock LLM response
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'content': [{'text': 'No recommendations available.'}]
            }).encode('utf-8'))
        }
        
        # Call get_recommendation
        result = get_recommendation("123", "casual dresses")
        
        # Verify result
        result_data = json.loads(result)
        assert 'items' in result_data
        assert len(result_data['items']) == 0
    
    @patch('runtime.strands_agent._personalize_rt')
    def test_get_recommendation_personalize_error(self, mock_personalize):
        """Test get_recommendation handles Personalize errors."""
        from runtime.strands_agent import get_recommendation
        
        # Mock Personalize error
        mock_personalize.get_recommendations.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Recommender not found'}},
            'GetRecommendations'
        )
        
        # Call get_recommendation
        result = get_recommendation("123", "casual dresses")
        
        # Verify error response
        result_data = json.loads(result)
        assert 'error' in result_data
    
    @patch('runtime.strands_agent._bedrock_rt')
    @patch('runtime.strands_agent._personalize_rt')
    @patch('runtime.strands_agent._get_user_info')
    def test_get_recommendation_bedrock_error(self, mock_get_user, mock_personalize, mock_bedrock):
        """Test get_recommendation handles Bedrock errors."""
        from runtime.strands_agent import get_recommendation
        
        # Mock user info
        mock_get_user.return_value = {
            'user_id': '123',
            'age': '25',
            'gender': 'F',
            'visited': [],
            'add_to_cart': [],
            'purchased': []
        }
        
        # Mock Personalize success
        mock_personalize.get_recommendations.return_value = {
            'itemList': [{'itemId': 'item-100'}]
        }
        
        # Mock Bedrock error
        mock_bedrock.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ModelNotReadyException', 'Message': 'Model not ready'}},
            'InvokeModel'
        )
        
        # Call get_recommendation
        result = get_recommendation("123", "casual dresses")
        
        # Verify error response
        result_data = json.loads(result)
        assert 'error' in result_data


class TestHelperFunctions:
    """Test helper functions for data retrieval."""
    
    @patch('runtime.strands_agent._dynamodb')
    def test_get_item_info_success(self, mock_dynamodb):
        """Test successful item info retrieval."""
        from runtime.strands_agent import _get_item_info
        
        # Mock DynamoDB table
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock query response
        mock_table.query.return_value = {
            'Items': [{
                'ITEM_ID': 'item-123',
                'NAME': 'Blue Dress',
                'PRICE': '49.99',
                'STYLE': 'casual'
            }]
        }
        
        # Call _get_item_info
        result = _get_item_info('item-123')
        
        # Verify result
        assert result['item_id'] == 'item-123'
        assert result['title'] == 'Blue Dress'
        assert result['price'] == '49.99'
        assert result['style'] == 'casual'
    
    @patch('runtime.strands_agent._dynamodb')
    def test_get_item_info_not_found(self, mock_dynamodb):
        """Test item info retrieval when item not found."""
        from runtime.strands_agent import _get_item_info
        
        # Mock DynamoDB table
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock query response with no items
        mock_table.query.return_value = {'Items': []}
        
        # Call _get_item_info
        result = _get_item_info('item-999')
        
        # Verify default result
        assert result['item_id'] == 'item-999'
        assert result['title'] == 'Unknown'
        assert result['price'] == '0'
        assert result['style'] == 'unknown'
    
    @patch('runtime.strands_agent._dynamodb')
    def test_get_item_info_error(self, mock_dynamodb):
        """Test item info retrieval handles errors gracefully."""
        from runtime.strands_agent import _get_item_info
        
        # Mock DynamoDB table
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock query error
        mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'Query'
        )
        
        # Call _get_item_info
        result = _get_item_info('item-123')
        
        # Verify default result
        assert result['item_id'] == 'item-123'
        assert result['title'] == 'Unknown'
    
    @patch('runtime.strands_agent._dynamodb')
    def test_get_user_info_success(self, mock_dynamodb):
        """Test successful user info retrieval."""
        from runtime.strands_agent import _get_user_info
        
        # Mock DynamoDB table
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock query response
        mock_table.query.return_value = {
            'Items': [{
                'USER_ID': 123,
                'AGE': 25,
                'GENDER': 'F',
                'VISITED': ['item-1', 'item-2'],
                'ADD_TO_CART': ['item-3'],
                'PURCHASED': ['item-4']
            }]
        }
        
        # Call _get_user_info
        result = _get_user_info('123')
        
        # Verify result
        assert result['user_id'] == '123'
        assert result['age'] == '25'
        assert result['gender'] == 'F'
        assert result['visited'] == ['item-1', 'item-2']
        assert result['add_to_cart'] == ['item-3']
        assert result['purchased'] == ['item-4']
    
    @patch('runtime.strands_agent._dynamodb')
    def test_get_user_info_not_found(self, mock_dynamodb):
        """Test user info retrieval when user not found."""
        from runtime.strands_agent import _get_user_info
        
        # Mock DynamoDB table
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock query response with no items
        mock_table.query.return_value = {'Items': []}
        
        # Call _get_user_info
        result = _get_user_info('999')
        
        # Verify default result
        assert result['user_id'] == '999'
        assert result['age'] == '?'
        assert result['gender'] == '?'
        assert result['visited'] == []


class TestOpenTelemetryConfiguration:
    """Test OpenTelemetry configuration."""
    
    @patch('runtime.strands_agent.trace')
    @patch('runtime.strands_agent.metrics')
    @patch.dict('os.environ', {'OTEL_SERVICE_NAME': 'test-service', 'STAGE': 'test'})
    def test_configure_opentelemetry(self, mock_metrics, mock_trace):
        """Test OpenTelemetry configuration."""
        from runtime.strands_agent import configure_opentelemetry
        
        # Call configuration
        configure_opentelemetry()
        
        # Verify tracer provider was set
        mock_trace.set_tracer_provider.assert_called_once()
        
        # Verify meter provider was set
        mock_metrics.set_meter_provider.assert_called_once()
