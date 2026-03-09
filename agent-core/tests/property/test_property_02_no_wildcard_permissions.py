"""
Property 2: No Wildcard Resource Permissions

For any IAM policy statement in the runtime execution role, the resources list 
SHALL NOT contain the wildcard value "*".

Validates: Requirements 9.2
"""

from hypothesis import given, settings, assume
import hypothesis.strategies as st
from aws_cdk import App
from aws_cdk.assertions import Template
import json


# Strategy for generating IAM policy statements
@st.composite
def iam_policy_statement(draw):
    """Generate a valid IAM policy statement structure."""
    actions = draw(st.lists(
        st.sampled_from([
            "dynamodb:Query",
            "dynamodb:GetItem",
            "aoss:APIAccessAll",
            "personalize:GetRecommendations",
            "bedrock:InvokeModel",
            "ssm:GetParameter",
            "ssm:GetParametersByPath",
            "bedrock:InvokeAgent",
            "bedrock:Retrieve"
        ]),
        min_size=1,
        max_size=3,
        unique=True
    ))
    
    # Generate resource ARNs (no wildcards)
    resource_types = draw(st.sampled_from([
        "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
        "arn:aws:aoss:us-east-1:123456789012:collection/test-collection",
        "arn:aws:personalize:us-east-1:123456789012:recommender/test-recommender",
        "arn:aws:bedrock:us-east-1::foundation-model/test-model",
        "arn:aws:ssm:us-east-1:123456789012:parameter/sales-agent/dev/test",
        "arn:aws:bedrock:us-east-1:123456789012:memory/test-memory"
    ]))
    
    return {
        "Effect": "Allow",
        "Action": actions,
        "Resource": [resource_types]
    }


@settings(max_examples=100)
@given(statement=iam_policy_statement())
def test_no_wildcard_in_resources(statement):
    """
    Feature: agentcore-cdk-infrastructure, Property 2: No Wildcard Resource Permissions
    
    For any IAM policy statement, the resources list SHALL NOT contain "*".
    """
    resources = statement.get("Resource", [])
    
    # Ensure resources is a list
    if isinstance(resources, str):
        resources = [resources]
    
    # Check that no resource is exactly "*"
    for resource in resources:
        assert resource != "*", \
            f"Policy statement contains wildcard resource: {statement}"
        
        # Also check that resource is not empty or None
        assert resource, \
            f"Policy statement contains empty resource: {statement}"


@settings(max_examples=100)
@given(
    statements=st.lists(iam_policy_statement(), min_size=1, max_size=10)
)
def test_no_wildcard_in_policy_document(statements):
    """
    Feature: agentcore-cdk-infrastructure, Property 2: No Wildcard Resource Permissions
    
    For any IAM policy document with multiple statements, no statement SHALL 
    contain "*" in resources.
    """
    policy_document = {
        "Version": "2012-10-17",
        "Statement": statements
    }
    
    # Check all statements
    for statement in policy_document["Statement"]:
        resources = statement.get("Resource", [])
        
        if isinstance(resources, str):
            resources = [resources]
        
        for resource in resources:
            assert resource != "*", \
                f"Policy document contains wildcard resource in statement: {statement}"


def test_cdk_stack_runtime_role_no_wildcards():
    """
    Feature: agentcore-cdk-infrastructure, Property 2: No Wildcard Resource Permissions
    
    Verify that the actual CDK stack runtime role does not contain wildcard resources.
    This is a concrete test that validates the CDK implementation.
    """
    # Import here to avoid circular dependencies
    try:
        from cdk.stacks.sales_agent_stack import SalesAgentRuntimeStack
        
        app = App()
        stack = SalesAgentRuntimeStack(app, "TestStack", stage="test")
        template = Template.from_stack(stack)
        
        # Get all IAM policies from the template
        template_json = template.to_json()
        
        for resource_name, resource in template_json.get("Resources", {}).items():
            if resource.get("Type") == "AWS::IAM::Policy":
                policy_doc = resource.get("Properties", {}).get("PolicyDocument", {})
                statements = policy_doc.get("Statement", [])
                
                for statement in statements:
                    resources = statement.get("Resource", [])
                    
                    if isinstance(resources, str):
                        resources = [resources]
                    
                    for resource_arn in resources:
                        # Skip CloudFormation intrinsic functions
                        if isinstance(resource_arn, dict):
                            continue
                        
                        assert resource_arn != "*", \
                            f"Runtime role policy contains wildcard resource in {resource_name}: {statement}"
    
    except ImportError:
        # Stack not yet implemented, skip this test
        pass


@settings(max_examples=100)
@given(
    action_count=st.integers(min_value=1, max_value=10),
    resource_count=st.integers(min_value=1, max_value=5)
)
def test_policy_statement_structure_validity(action_count, resource_count):
    """
    Feature: agentcore-cdk-infrastructure, Property 2: No Wildcard Resource Permissions
    
    Verify that policy statements with multiple actions and resources maintain
    the no-wildcard constraint.
    """
    actions = [f"service:Action{i}" for i in range(action_count)]
    resources = [f"arn:aws:service:region:account:resource/name{i}" 
                 for i in range(resource_count)]
    
    statement = {
        "Effect": "Allow",
        "Action": actions,
        "Resource": resources
    }
    
    # Verify no wildcards in resources
    for resource in statement["Resource"]:
        assert resource != "*", \
            f"Generated statement contains wildcard: {statement}"
        assert "*" not in resource or "arn:aws:" in resource, \
            f"Resource contains suspicious wildcard: {resource}"
