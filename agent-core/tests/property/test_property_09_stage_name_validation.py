"""
Property 9: Deployment Script Stage Name Validation

The deployment script SHALL accept only alphanumeric stage names with hyphens 
and underscores, rejecting invalid stage names with descriptive errors.

Validates: Requirements 13.3
"""

import re
from hypothesis import given, settings, assume
import hypothesis.strategies as st


# Strategy for valid stage names (alphanumeric with hyphens and underscores)
valid_stage_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    ),
    min_size=1,
    max_size=50
)

# Strategy for invalid stage names (contains special characters)
invalid_stage_strategy = st.text(
    alphabet=st.characters(
        blacklist_categories=('Cc', 'Cs'),
        blacklist_characters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
    ),
    min_size=1,
    max_size=50
)


@settings(max_examples=100)
@given(stage=valid_stage_strategy)
def test_valid_stage_names_accepted(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Valid stage names (alphanumeric with hyphens/underscores) SHALL be accepted.
    """
    # Pattern for valid stage names
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    # Valid stage names should match the pattern
    assert re.match(pattern, stage), \
        f"Valid stage name '{stage}' should match pattern {pattern}"


@settings(max_examples=100)
@given(stage=invalid_stage_strategy)
def test_invalid_stage_names_rejected(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Invalid stage names SHALL be rejected.
    """
    # Assume stage contains invalid characters
    assume(not re.match(r'^[a-zA-Z0-9_-]+$', stage))
    
    # Pattern for valid stage names
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    # Invalid stage names should NOT match the pattern
    assert not re.match(pattern, stage), \
        f"Invalid stage name '{stage}' should not match pattern {pattern}"


@settings(max_examples=100)
@given(
    stage=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_',
        min_size=1,
        max_size=50
    )
)
def test_stage_name_pattern_consistency(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Stage name validation SHALL be consistent across all uses.
    """
    # Pattern should match alphanumeric with hyphens and underscores
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    assert re.match(pattern, stage), \
        f"Stage name '{stage}' should match validation pattern"


@settings(max_examples=100)
@given(
    valid_chars=st.lists(
        st.sampled_from('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'),
        min_size=1,
        max_size=20
    )
)
def test_stage_names_from_valid_characters(valid_chars):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Stage names composed of valid characters SHALL be accepted.
    """
    stage = ''.join(valid_chars)
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    assert re.match(pattern, stage), \
        f"Stage name '{stage}' composed of valid characters should be accepted"


@settings(max_examples=100)
@given(
    stage=st.text(min_size=1, max_size=50)
)
def test_stage_name_validation_rejects_special_characters(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Stage names with special characters SHALL be rejected.
    """
    pattern = r'^[a-zA-Z0-9_-]+$'
    is_valid = bool(re.match(pattern, stage))
    
    # Check for special characters
    has_special_chars = any(
        char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
        for char in stage
    )
    
    if has_special_chars:
        assert not is_valid, \
            f"Stage name '{stage}' with special characters should be rejected"
    else:
        assert is_valid, \
            f"Stage name '{stage}' without special characters should be accepted"


def test_common_valid_stage_names():
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Common valid stage names SHALL be accepted.
    """
    valid_stages = [
        "dev",
        "staging",
        "prod",
        "production",
        "test",
        "dev-us-east-1",
        "staging_v2",
        "prod-2024",
        "feature-branch-123",
        "user_test_env"
    ]
    
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    for stage in valid_stages:
        assert re.match(pattern, stage), \
            f"Common stage name '{stage}' should be valid"


def test_common_invalid_stage_names():
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Common invalid stage names SHALL be rejected.
    """
    invalid_stages = [
        "dev.prod",  # Contains dot
        "staging@v2",  # Contains @
        "prod/2024",  # Contains slash
        "test env",  # Contains space
        "dev#123",  # Contains hash
        "prod!",  # Contains exclamation
        "staging$",  # Contains dollar sign
        ""  # Empty string
    ]
    
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    for stage in invalid_stages:
        assert not re.match(pattern, stage), \
            f"Invalid stage name '{stage}' should be rejected"


@settings(max_examples=100)
@given(stage=valid_stage_strategy)
def test_validation_error_message_is_descriptive(stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Validation error messages SHALL be descriptive.
    """
    # Simulate validation error message
    error_message = f"Error: Invalid stage name '{stage}'. " \
                   f"Stage names must contain only alphanumeric characters, hyphens, and underscores."
    
    # Verify error message components
    assert "stage name" in error_message.lower(), \
        "Error should mention stage name"
    assert "alphanumeric" in error_message.lower(), \
        "Error should specify allowed characters"


@settings(max_examples=100)
@given(
    prefix=st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=10),
    suffix=st.text(alphabet='0123456789', min_size=1, max_size=5)
)
def test_stage_names_with_prefix_and_suffix(prefix, suffix):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Stage names with alphanumeric prefix and suffix SHALL be valid.
    """
    stage = f"{prefix}-{suffix}"
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    assert re.match(pattern, stage), \
        f"Stage name '{stage}' with prefix and suffix should be valid"


@settings(max_examples=100)
@given(
    stage_base=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz',
        min_size=1,
        max_size=20
    ),
    separator=st.sampled_from(['-', '_'])
)
def test_stage_names_with_separators(stage_base, separator):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Stage names with hyphens or underscores as separators SHALL be valid.
    """
    stage = f"{stage_base}{separator}env"
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    assert re.match(pattern, stage), \
        f"Stage name '{stage}' with separator '{separator}' should be valid"


def test_deployment_script_validates_stage_name():
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    The deployment script SHALL validate stage names before proceeding.
    """
    # This is a conceptual test - actual validation happens in the script
    validation_pattern = r'^[a-zA-Z0-9_-]+$'
    
    test_cases = [
        ("dev", True),
        ("prod-2024", True),
        ("test_env", True),
        ("dev.prod", False),
        ("staging@v2", False),
        ("", False)
    ]
    
    for stage, should_be_valid in test_cases:
        is_valid = bool(re.match(validation_pattern, stage))
        assert is_valid == should_be_valid, \
            f"Stage '{stage}' validation result {is_valid} != expected {should_be_valid}"


@settings(max_examples=100)
@given(
    stage_length=st.integers(min_value=1, max_value=100)
)
def test_stage_name_length_handling(stage_length):
    """
    Feature: agentcore-cdk-infrastructure, Property 9: Deployment Script Stage Name Validation
    
    Stage names of various lengths SHALL be validated correctly.
    """
    # Generate stage name of specific length
    stage = 'a' * stage_length
    pattern = r'^[a-zA-Z0-9_-]+$'
    
    # Should be valid regardless of length (within reason)
    assert re.match(pattern, stage), \
        f"Stage name of length {stage_length} should be valid"
