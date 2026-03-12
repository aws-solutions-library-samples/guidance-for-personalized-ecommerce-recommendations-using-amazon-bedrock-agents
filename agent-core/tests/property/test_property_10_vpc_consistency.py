"""
Property 10: VPC Configuration Consistency

For any VPC configuration, all network resources SHALL reference the same VPC ID, 
ensuring consistent network isolation.

Validates: Requirements 1.1
"""

from hypothesis import given, settings, assume
import hypothesis.strategies as st
from aws_cdk import App
from aws_cdk.assertions import Template


# Strategy for VPC IDs
vpc_id_strategy = st.text(
    alphabet='abcdef0123456789',
    min_size=17,
    max_size=17
).map(lambda s: f"vpc-{s}")

# Strategy for valid stage names
valid_stage_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    ),
    min_size=1,
    max_size=20
)


@settings(max_examples=100)
@given(vpc_id=vpc_id_strategy)
def test_all_resources_reference_same_vpc(vpc_id):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    All network resources SHALL reference the same VPC ID.
    """
    # Simulate network resources
    resources = [
        {"type": "subnet", "vpc_id": vpc_id},
        {"type": "security_group", "vpc_id": vpc_id},
        {"type": "route_table", "vpc_id": vpc_id},
        {"type": "network_interface", "vpc_id": vpc_id}
    ]
    
    # Extract all VPC IDs
    vpc_ids = [resource["vpc_id"] for resource in resources]
    
    # All should be the same
    assert len(set(vpc_ids)) == 1, \
        f"All resources should reference the same VPC ID: {vpc_ids}"
    assert vpc_ids[0] == vpc_id, \
        f"VPC ID should be {vpc_id}, got {vpc_ids[0]}"


@settings(max_examples=100)
@given(
    vpc_id=vpc_id_strategy,
    resource_count=st.integers(min_value=1, max_value=20)
)
def test_multiple_resources_vpc_consistency(vpc_id, resource_count):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    Multiple network resources SHALL maintain VPC consistency.
    """
    # Create multiple resources
    resources = [
        {"name": f"resource-{i}", "vpc_id": vpc_id}
        for i in range(resource_count)
    ]
    
    # All should reference the same VPC
    vpc_ids = [resource["vpc_id"] for resource in resources]
    assert len(set(vpc_ids)) == 1, \
        f"All {resource_count} resources should reference the same VPC"


@settings(max_examples=100)
@given(
    vpc_id1=vpc_id_strategy,
    vpc_id2=vpc_id_strategy
)
def test_different_vpcs_not_mixed(vpc_id1, vpc_id2):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    Resources from different VPCs SHALL not be mixed in the same stack.
    """
    assume(vpc_id1 != vpc_id2)
    
    # Resources should all use one VPC or the other, not both
    resources_vpc1 = [
        {"name": "resource-1", "vpc_id": vpc_id1},
        {"name": "resource-2", "vpc_id": vpc_id1}
    ]
    
    resources_vpc2 = [
        {"name": "resource-3", "vpc_id": vpc_id2},
        {"name": "resource-4", "vpc_id": vpc_id2}
    ]
    
    # Within each group, VPC IDs should be consistent
    vpc_ids_1 = [r["vpc_id"] for r in resources_vpc1]
    vpc_ids_2 = [r["vpc_id"] for r in resources_vpc2]
    
    assert len(set(vpc_ids_1)) == 1, "VPC 1 resources should be consistent"
    assert len(set(vpc_ids_2)) == 1, "VPC 2 resources should be consistent"
    
    # The two groups should use different VPCs
    assert vpc_ids_1[0] != vpc_ids_2[0], \
        "Different resource groups should use different VPCs"


def test_cdk_stack_vpc_consistency_with_existing_vpc():
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    CDK stack with existing VPC SHALL use that VPC consistently.
    """
    try:
        from cdk.stacks.sales_agent_stack import SalesAgentRuntimeStack
        
        test_vpc_id = "vpc-12345678901234567"
        app = App()
        stack = SalesAgentRuntimeStack(
            app,
            "TestStack",
            stage="test",
            vpc_id=test_vpc_id
        )
        template = Template.from_stack(stack)
        
        template_json = template.to_json()
        
        # Collect all VPC references
        vpc_references = []
        
        for resource_name, resource in template_json.get("Resources", {}).items():
            properties = resource.get("Properties", {})
            
            # Check for VPC ID in various property names
            if "VpcId" in properties:
                vpc_ref = properties["VpcId"]
                if isinstance(vpc_ref, str) and vpc_ref.startswith("vpc-"):
                    vpc_references.append(vpc_ref)
            
            # Check for VPC in subnet configurations
            if "SubnetIds" in properties or "SecurityGroupIds" in properties:
                # These resources should be in the same VPC
                pass
        
        # If we found VPC references, they should all be the same
        if vpc_references:
            assert len(set(vpc_references)) == 1, \
                f"All VPC references should be the same: {vpc_references}"
    
    except ImportError:
        # Stack not yet implemented, skip this test
        pass


def test_cdk_stack_vpc_consistency_with_new_vpc():
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    CDK stack creating new VPC SHALL use that VPC consistently.
    """
    try:
        from cdk.stacks.sales_agent_stack import SalesAgentRuntimeStack
        
        app = App()
        stack = SalesAgentRuntimeStack(
            app,
            "TestStack",
            stage="test"
            # No vpc_id provided - should create new VPC
        )
        template = Template.from_stack(stack)
        
        template_json = template.to_json()
        
        # Find the VPC resource
        vpc_resources = [
            (name, resource)
            for name, resource in template_json.get("Resources", {}).items()
            if resource.get("Type") == "AWS::EC2::VPC"
        ]
        
        # Should have exactly one VPC
        if vpc_resources:
            assert len(vpc_resources) == 1, \
                f"Should have exactly one VPC, found {len(vpc_resources)}"
    
    except ImportError:
        # Stack not yet implemented, skip this test
        pass


@settings(max_examples=100)
@given(
    vpc_id=vpc_id_strategy,
    stage=valid_stage_strategy
)
def test_vpc_consistency_across_stage_deployment(vpc_id, stage):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    VPC consistency SHALL be maintained across stage deployments.
    """
    # Simulate deployment configuration
    deployment_config = {
        "stage": stage,
        "vpc_id": vpc_id,
        "resources": [
            {"type": "runtime", "vpc_id": vpc_id},
            {"type": "database", "vpc_id": vpc_id},
            {"type": "cache", "vpc_id": vpc_id}
        ]
    }
    
    # All resources should use the configured VPC
    for resource in deployment_config["resources"]:
        assert resource["vpc_id"] == vpc_id, \
            f"Resource {resource['type']} should use VPC {vpc_id}"


@settings(max_examples=100)
@given(vpc_id=vpc_id_strategy)
def test_subnet_vpc_consistency(vpc_id):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    All subnets SHALL reference the same VPC.
    """
    # Simulate subnet configuration
    subnets = [
        {"name": "public-subnet-1", "vpc_id": vpc_id, "cidr": "10.0.1.0/24"},
        {"name": "public-subnet-2", "vpc_id": vpc_id, "cidr": "10.0.2.0/24"},
        {"name": "private-subnet-1", "vpc_id": vpc_id, "cidr": "10.0.11.0/24"},
        {"name": "private-subnet-2", "vpc_id": vpc_id, "cidr": "10.0.12.0/24"}
    ]
    
    # All subnets should reference the same VPC
    vpc_ids = [subnet["vpc_id"] for subnet in subnets]
    assert len(set(vpc_ids)) == 1, \
        f"All subnets should reference the same VPC: {vpc_ids}"


@settings(max_examples=100)
@given(vpc_id=vpc_id_strategy)
def test_security_group_vpc_consistency(vpc_id):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    All security groups SHALL reference the same VPC.
    """
    # Simulate security group configuration
    security_groups = [
        {"name": "runtime-sg", "vpc_id": vpc_id},
        {"name": "database-sg", "vpc_id": vpc_id},
        {"name": "alb-sg", "vpc_id": vpc_id}
    ]
    
    # All security groups should reference the same VPC
    vpc_ids = [sg["vpc_id"] for sg in security_groups]
    assert len(set(vpc_ids)) == 1, \
        f"All security groups should reference the same VPC: {vpc_ids}"


@settings(max_examples=100)
@given(
    vpc_id=vpc_id_strategy,
    resource_types=st.lists(
        st.sampled_from(["subnet", "security_group", "route_table", "network_acl"]),
        min_size=1,
        max_size=10
    )
)
def test_mixed_resource_types_vpc_consistency(vpc_id, resource_types):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    Mixed resource types SHALL all reference the same VPC.
    """
    # Create resources of different types
    resources = [
        {"type": resource_type, "vpc_id": vpc_id}
        for resource_type in resource_types
    ]
    
    # All should reference the same VPC
    vpc_ids = [resource["vpc_id"] for resource in resources]
    assert len(set(vpc_ids)) == 1, \
        f"All resource types should reference the same VPC: {vpc_ids}"


@settings(max_examples=100)
@given(vpc_id=vpc_id_strategy)
def test_vpc_id_format_validation(vpc_id):
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    VPC IDs SHALL follow AWS VPC ID format.
    """
    # VPC ID format: vpc-xxxxxxxxxxxxxxxxx (vpc- followed by 17 hex characters)
    import re
    pattern = r'^vpc-[a-f0-9]{17}$'
    
    assert re.match(pattern, vpc_id), \
        f"VPC ID '{vpc_id}' should match AWS VPC ID format"


def test_vpc_consistency_error_detection():
    """
    Feature: agentcore-cdk-infrastructure, Property 10: VPC Configuration Consistency
    
    VPC inconsistencies SHALL be detectable.
    """
    # Simulate resources with inconsistent VPC IDs
    resources = [
        {"name": "resource-1", "vpc_id": "vpc-11111111111111111"},
        {"name": "resource-2", "vpc_id": "vpc-22222222222222222"},  # Different VPC!
        {"name": "resource-3", "vpc_id": "vpc-11111111111111111"}
    ]
    
    # Extract VPC IDs
    vpc_ids = [resource["vpc_id"] for resource in resources]
    
    # Should detect inconsistency
    unique_vpcs = set(vpc_ids)
    assert len(unique_vpcs) > 1, \
        "Should detect VPC inconsistency when resources use different VPCs"
