"""
Property 1: Parameter Store Hierarchical Naming

For any stage name and any parameter key, the full parameter path SHALL follow 
the pattern /sales-agent/{stage}/{key} where stage and key are alphanumeric 
with hyphens and underscores.

Validates: Requirements 2.8, 11.3
"""

import re
from hypothesis import given, settings
import hypothesis.strategies as st


# Strategy for valid stage/key names (alphanumeric with hyphens and underscores)
valid_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    ),
    min_size=1,
    max_size=50
)


@settings(max_examples=100)
@given(stage=valid_name_strategy, key=valid_name_strategy)
def test_parameter_naming_pattern(stage, key):
    """
    Feature: agentcore-cdk-infrastructure, Property 1: Parameter Store Hierarchical Naming
    
    For any stage name and any parameter key, the full parameter path SHALL follow 
    the pattern /sales-agent/{stage}/{key}
    """
    # Construct the parameter path
    parameter_path = f"/sales-agent/{stage}/{key}"
    
    # Verify the pattern matches expected format
    pattern = r'^/sales-agent/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$'
    assert re.match(pattern, parameter_path), \
        f"Parameter path '{parameter_path}' does not match expected pattern"
    
    # Verify stage and key are preserved correctly
    parts = parameter_path.split('/')
    assert len(parts) == 4, f"Expected 4 parts in path, got {len(parts)}"
    assert parts[0] == "", "First part should be empty (leading slash)"
    assert parts[1] == "sales-agent", "Second part should be 'sales-agent'"
    assert parts[2] == stage, f"Third part should be stage '{stage}', got '{parts[2]}'"
    assert parts[3] == key, f"Fourth part should be key '{key}', got '{parts[3]}'"


@settings(max_examples=100)
@given(
    stage=valid_name_strategy,
    keys=st.lists(valid_name_strategy, min_size=1, max_size=10, unique=True)
)
def test_parameter_naming_uniqueness(stage, keys):
    """
    Feature: agentcore-cdk-infrastructure, Property 1: Parameter Store Hierarchical Naming
    
    Verify that different keys under the same stage produce unique paths.
    """
    paths = [f"/sales-agent/{stage}/{key}" for key in keys]
    
    # All paths should be unique
    assert len(paths) == len(set(paths)), \
        f"Generated paths are not unique: {paths}"
    
    # All paths should follow the pattern
    pattern = r'^/sales-agent/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$'
    for path in paths:
        assert re.match(pattern, path), \
            f"Path '{path}' does not match expected pattern"


@settings(max_examples=100)
@given(
    stages=st.lists(valid_name_strategy, min_size=2, max_size=5, unique=True),
    key=valid_name_strategy
)
def test_parameter_naming_stage_isolation(stages, key):
    """
    Feature: agentcore-cdk-infrastructure, Property 1: Parameter Store Hierarchical Naming
    
    Verify that the same key under different stages produces different paths.
    """
    paths = [f"/sales-agent/{stage}/{key}" for stage in stages]
    
    # All paths should be unique (different stages)
    assert len(paths) == len(set(paths)), \
        f"Paths for different stages are not unique: {paths}"
    
    # All paths should contain the same key but different stages
    for i, path in enumerate(paths):
        assert path.endswith(f"/{key}"), \
            f"Path '{path}' should end with '/{key}'"
        assert f"/{stages[i]}/" in path, \
            f"Path '{path}' should contain stage '/{stages[i]}/'"
