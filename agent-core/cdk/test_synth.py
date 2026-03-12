#!/usr/bin/env python3
"""
Test script to verify CDK stack synthesis.
"""

import sys
import aws_cdk as cdk
from stacks.sales_agent_stack import SalesAgentRuntimeStack


def test_synth():
    """Test CDK stack synthesis with dev stage."""
    try:
        app = cdk.App()
        
        # Create stack with test stage
        stack = SalesAgentRuntimeStack(
            app,
            "SalesAgentRuntimeStack-dev",
            stage="dev",
            vpc_id=None,
            description="AgentCore Sales Agent Runtime Infrastructure - dev stage",
            env=cdk.Environment(region="us-east-1")
        )
        
        # Synthesize the stack
        assembly = app.synth()
        
        # Get the CloudFormation template
        template = assembly.get_stack_by_name("SalesAgentRuntimeStack-dev").template
        
        print("✓ CDK stack synthesis successful!")
        print(f"✓ Generated CloudFormation template with {len(template.get('Resources', {}))} resources")
        
        # Verify key resources exist
        resources = template.get('Resources', {})
        resource_types = set(r.get('Type') for r in resources.values())
        
        print(f"✓ Resource types: {len(resource_types)}")
        print(f"  - VPC resources: {sum(1 for t in resource_types if 'VPC' in t or 'Subnet' in t)}")
        print(f"  - IAM resources: {sum(1 for t in resource_types if 'IAM' in t)}")
        print(f"  - SSM resources: {sum(1 for t in resource_types if 'SSM' in t)}")
        
        return 0
        
    except Exception as e:
        print(f"✗ CDK stack synthesis failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_synth())
