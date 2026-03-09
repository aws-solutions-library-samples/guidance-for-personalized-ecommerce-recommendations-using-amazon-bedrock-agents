#!/usr/bin/env python3
"""
Check if we can find the AgentCore Runtime ARN.
"""

import boto3
import json

# Initialize clients
agentcore = boto3.client('bedrock-agentcore', region_name='us-east-1')
cfn = boto3.client('cloudformation', region_name='us-east-1')

print("Checking CloudFormation stacks for Runtime ARN...")
print("=" * 60)

# Check RuntimeStack outputs
try:
    response = cfn.describe_stacks(StackName='RuntimeStack-alpha')
    stack = response['Stacks'][0]
    
    print("\nRuntimeStack-alpha Outputs:")
    for output in stack.get('Outputs', []):
        print(f"  {output['OutputKey']}: {output['OutputValue']}")
        if 'runtime' in output['OutputKey'].lower() or 'arn' in output['OutputKey'].lower():
            print(f"    ^^^ Potential Runtime ARN")
    
    # Check for tags
    print("\nRuntimeStack-alpha Tags:")
    for tag in stack.get('Tags', []):
        print(f"  {tag['Key']}: {tag['Value']}")
        
except Exception as e:
    print(f"Error checking RuntimeStack: {e}")

# Check InfrastructureStack outputs
try:
    response = cfn.describe_stacks(StackName='InfrastructureStack-alpha')
    stack = response['Stacks'][0]
    
    print("\nInfrastructureStack-alpha Outputs:")
    for output in stack.get('Outputs', []):
        print(f"  {output['OutputKey']}: {output['OutputValue']}")
        if 'runtime' in output['OutputKey'].lower() or 'arn' in output['OutputKey'].lower():
            print(f"    ^^^ Potential Runtime ARN")
            
except Exception as e:
    print(f"Error checking InfrastructureStack: {e}")

# Try to list ECS services to construct potential ARN
print("\n" + "=" * 60)
print("Checking ECS for runtime information...")
print("=" * 60)

try:
    ecs = boto3.client('ecs', region_name='us-east-1')
    
    # List clusters
    clusters = ecs.list_clusters()
    print(f"\nECS Clusters: {clusters.get('clusterArns', [])}")
    
    # Get services in sales-agent-alpha cluster
    services = ecs.list_services(cluster='sales-agent-alpha')
    print(f"\nECS Services in sales-agent-alpha:")
    for service_arn in services.get('serviceArns', []):
        print(f"  {service_arn}")
        
        # Describe service
        service_details = ecs.describe_services(
            cluster='sales-agent-alpha',
            services=[service_arn]
        )
        
        for service in service_details.get('services', []):
            print(f"\n  Service Name: {service['serviceName']}")
            print(f"  Service ARN: {service['serviceArn']}")
            print(f"  Task Definition: {service['taskDefinition']}")
            print(f"  Load Balancers: {service.get('loadBalancers', [])}")
            
except Exception as e:
    print(f"Error checking ECS: {e}")

print("\n" + "=" * 60)
print("Note: The AgentCore Runtime ARN should be in the format:")
print("  arn:aws:bedrock-agentcore:region:account:agent-runtime/runtime-id")
print("=" * 60)
