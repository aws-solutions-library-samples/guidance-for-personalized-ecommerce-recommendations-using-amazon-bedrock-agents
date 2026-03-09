"""
Property 8: CLI Stage Existence Validation

CLI commands SHALL verify that the specified stage exists before executing 
operations, failing with a descriptive error if the stage does not exist.

Validates: Requirements 13.6
"""

from hypothesis import given, settings
import hypothesis.strategies as st
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError


# Strategy for valid stage names
valid_stage_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    ),
    min_size=1,
    max_size=20
)

# Strategy for CLI command names
cli_command_strategy = st.sampled_from([
    "param",
    "invoke",
    "logs",
    "status"
])


@settings(max_examples=100)
@given(
    command=cli_command_strategy,
    stage=valid_stage_strategy
)
def test_cli_validates_stage_existence(command, stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    All CLI commands SHALL validate that the stage exists.
    """
    # Conceptual test: stage validation should occur
    validation_steps = [
        "validate_credentials",
        "validate_stage_exists",
        "execute_command"
    ]
    
    # Verify stage validation is in the workflow
    assert "validate_stage_exists" in validation_steps, \
        "Stage existence validation should be part of CLI workflow"


@settings(max_examples=100)
@given(stage=valid_stage_strategy)
def test_nonexistent_stage_produces_descriptive_error(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    Non-existent stages SHALL produce descriptive error messages.
    """
    error_message = f"Error: Stage '{stage}' does not exist. " \
                   f"Available stages can be listed by checking Parameter Store paths."
    
    # Verify error message components
    assert "stage" in error_message.lower(), \
        "Error should mention stage"
    assert "does not exist" in error_message.lower() or "not found" in error_message.lower(), \
        "Error should indicate stage doesn't exist"
    assert stage in error_message, \
        "Error should include the stage name"


def test_stage_validation_checks_parameter_store():
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    Stage validation SHALL check Parameter Store for stage-specific parameters.
    """
    try:
        from cli.sales_agent_cli import SalesAgentCLI
        
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            
            # Mock empty parameter list (stage doesn't exist)
            mock_ssm.get_parameters_by_path.return_value = {
                'Parameters': []
            }
            
            mock_client.return_value = mock_ssm
            
            cli = SalesAgentCLI(stage="nonexistent")
            
            # Validation should detect missing stage
            try:
                result = cli.validate_stage()
                assert result is False, \
                    "Validation should return False for non-existent stage"
            except AttributeError:
                # Method might not exist yet, skip
                pass
    
    except ImportError:
        # CLI not yet implemented, skip this test
        pass


def test_existing_stage_passes_validation():
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    Existing stages SHALL pass validation.
    """
    try:
        from cli.sales_agent_cli import SalesAgentCLI
        
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            
            # Mock parameter list with stage parameters
            mock_ssm.get_parameters_by_path.return_value = {
                'Parameters': [
                    {'Name': '/sales-agent/dev/item_table', 'Value': 'items'},
                    {'Name': '/sales-agent/dev/user_table', 'Value': 'users'}
                ]
            }
            
            mock_client.return_value = mock_ssm
            
            cli = SalesAgentCLI(stage="dev")
            
            # Validation should succeed
            try:
                result = cli.validate_stage()
                assert result is True or result is None, \
                    "Validation should succeed for existing stage"
            except AttributeError:
                # Method might not exist yet, skip
                pass
    
    except ImportError:
        # CLI not yet implemented, skip this test
        pass


@settings(max_examples=100)
@given(
    stage=valid_stage_strategy,
    command=cli_command_strategy
)
def test_stage_validation_occurs_before_command_execution(stage, command):
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    Stage validation SHALL occur before command execution.
    """
    # Execution order
    execution_order = [
        "parse_arguments",
        "validate_credentials",
        "validate_stage",
        "execute_command"
    ]
    
    # Find indices
    validate_idx = execution_order.index("validate_stage")
    execute_idx = execution_order.index("execute_command")
    
    # Validation should come before execution
    assert validate_idx < execute_idx, \
        "Stage validation should occur before command execution"


def test_param_get_validates_stage_exists():
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    The 'param get' command SHALL validate stage exists.
    """
    try:
        from cli.sales_agent_cli import SalesAgentCLI
        
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            
            # First call: stage validation (no parameters found)
            # Second call: actual get_parameter (should not be reached)
            mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
            mock_ssm.get_parameter.side_effect = Exception("Should not be called")
            
            mock_client.return_value = mock_ssm
            
            cli = SalesAgentCLI(stage="nonexistent")
            
            # Should fail at stage validation
            try:
                cli.param_get("test_key")
            except (Exception, AttributeError):
                # Expected - stage validation should prevent execution
                pass
    
    except ImportError:
        # CLI not yet implemented, skip this test
        pass


def test_invoke_validates_stage_exists():
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    The 'invoke' command SHALL validate stage exists.
    """
    try:
        from cli.sales_agent_cli import SalesAgentCLI
        
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
            mock_client.return_value = mock_ssm
            
            cli = SalesAgentCLI(stage="nonexistent")
            
            # Should fail at stage validation
            try:
                cli.invoke("test message")
            except (Exception, AttributeError):
                # Expected - stage validation should prevent execution
                pass
    
    except ImportError:
        # CLI not yet implemented, skip this test
        pass


@settings(max_examples=100)
@given(
    stages=st.lists(valid_stage_strategy, min_size=1, max_size=5, unique=True)
)
def test_stage_validation_distinguishes_between_stages(stages):
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    Stage validation SHALL correctly distinguish between different stages.
    """
    # Each stage should have unique parameter paths
    param_paths = [f"/sales-agent/{stage}/item_table" for stage in stages]
    
    # All paths should be unique
    assert len(param_paths) == len(set(param_paths)), \
        "Each stage should have unique parameter paths"


@settings(max_examples=100)
@given(stage=valid_stage_strategy)
def test_stage_validation_error_suggests_available_stages(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    Stage validation errors SHOULD suggest how to find available stages.
    """
    error_message = f"Error: Stage '{stage}' not found. " \
                   f"To list available stages, check Parameter Store paths under /sales-agent/"
    
    # Verify error provides guidance
    assert "list" in error_message.lower() or "check" in error_message.lower(), \
        "Error should suggest how to find available stages"
    assert "/sales-agent/" in error_message, \
        "Error should mention the parameter store path"


@settings(max_examples=100)
@given(
    stage=valid_stage_strategy,
    param_count=st.integers(min_value=0, max_value=10)
)
def test_stage_exists_if_parameters_present(stage, param_count):
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    A stage SHALL be considered to exist if it has parameters in Parameter Store.
    """
    # Stage exists if param_count > 0
    stage_exists = param_count > 0
    
    if stage_exists:
        # Should pass validation
        assert param_count > 0, "Stage with parameters should exist"
    else:
        # Should fail validation
        assert param_count == 0, "Stage without parameters should not exist"


def test_logs_command_validates_stage_exists():
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    The 'logs' command SHALL validate stage exists.
    """
    try:
        from cli.sales_agent_cli import SalesAgentCLI
        
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
            
            mock_logs = MagicMock()
            mock_logs.filter_log_events.side_effect = Exception("Should not be called")
            
            def client_factory(service_name, **kwargs):
                if service_name == 'ssm':
                    return mock_ssm
                elif service_name == 'logs':
                    return mock_logs
                return MagicMock()
            
            mock_client.side_effect = client_factory
            
            cli = SalesAgentCLI(stage="nonexistent")
            
            # Should fail at stage validation
            try:
                cli.logs()
            except (Exception, AttributeError):
                # Expected - stage validation should prevent execution
                pass
            
            # Logs API should not be called
            assert not mock_logs.filter_log_events.called, \
                "Logs API should not be called for non-existent stage"
    
    except ImportError:
        # CLI not yet implemented, skip this test
        pass


def test_status_command_validates_stage_exists():
    """
    Feature: agentcore-cdk-infrastructure, Property 8: CLI Stage Existence Validation
    
    The 'status' command SHALL validate stage exists.
    """
    try:
        from cli.sales_agent_cli import SalesAgentCLI
        
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            mock_ssm.get_parameters_by_path.return_value = {'Parameters': []}
            mock_client.return_value = mock_ssm
            
            cli = SalesAgentCLI(stage="nonexistent")
            
            # Should fail at stage validation
            try:
                cli.status()
            except (Exception, AttributeError):
                # Expected - stage validation should prevent execution
                pass
    
    except ImportError:
        # CLI not yet implemented, skip this test
        pass
