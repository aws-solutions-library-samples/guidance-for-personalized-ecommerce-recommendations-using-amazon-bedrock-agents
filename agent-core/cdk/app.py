#!/usr/bin/env python3
"""
CDK Application Entry Point for AgentCore Sales Agent Runtime Infrastructure.

This application supports two deployment modes:
1. Bootstrap mode: Creates CodeCommit, CodePipeline, and CodeBuild infrastructure
2. Normal mode: Creates InfrastructureStack and RuntimeStack (deployed by CodeBuild)
"""

import os
import aws_cdk as cdk
from stacks.bootstrap_stack import BootstrapStack
from stacks.infrastructure_stack import InfrastructureStack
from stacks.runtime_stack import RuntimeStack


def main():
    """Initialize CDK app and create stacks based on deployment mode."""
    app = cdk.App()
    
    # Get context parameters
    stage = app.node.try_get_context("stage")
    bootstrap_mode = app.node.try_get_context("bootstrap")
    
    # Validate required parameters
    if not stage:
        raise ValueError(
            "Stage parameter is required. "
            "Provide via: cdk deploy --context stage=<stage-name>"
        )
    
    # Get account and region from environment or CDK defaults
    account = (
        app.node.try_get_context("account") or
        os.environ.get("CDK_DEFAULT_ACCOUNT") or
        os.environ.get("AWS_ACCOUNT_ID")
    )
    region = (
        app.node.try_get_context("region") or
        os.environ.get("CDK_DEFAULT_REGION") or
        os.environ.get("AWS_DEFAULT_REGION") or
        os.environ.get("AWS_REGION") or
        "us-east-1"
    )
    
    env = cdk.Environment(account=account, region=region)
    
    # Bootstrap mode: Deploy minimal CI/CD infrastructure
    if bootstrap_mode == "true":
        # Get required parameters for bootstrap
        item_table = app.node.try_get_context("itemTable")
        user_table = app.node.try_get_context("userTable")
        aoss_endpoint = app.node.try_get_context("aossEndpoint")
        personalize_arn = app.node.try_get_context("personalizeArn")
        vpc_id = app.node.try_get_context("vpcId")
        
        # Validate required bootstrap parameters
        if not all([item_table, user_table, aoss_endpoint, personalize_arn]):
            raise ValueError(
                "Bootstrap mode requires: itemTable, userTable, aossEndpoint, personalizeArn. "
                "Provide via: cdk deploy --context bootstrap=true "
                "--context itemTable=<name> --context userTable=<name> "
                "--context aossEndpoint=<url> --context personalizeArn=<arn>"
            )
        
        BootstrapStack(
            app,
            f"BootstrapStack-{stage}",
            stage=stage,
            item_table=item_table,
            user_table=user_table,
            aoss_endpoint=aoss_endpoint,
            personalize_arn=personalize_arn,
            vpc_id=vpc_id,
            description=f"Bootstrap CI/CD infrastructure for Sales Agent - {stage} stage",
            env=env,
        )
    
    # Normal mode: Deploy infrastructure and runtime stacks (called by CodeBuild)
    else:
        vpc_id = app.node.try_get_context("vpcId")
        
        # Create InfrastructureStack
        infra_stack = InfrastructureStack(
            app,
            f"InfrastructureStack-{stage}",
            stage=stage,
            vpc_id=vpc_id,
            description=f"Core infrastructure for Sales Agent - {stage} stage",
            env=env,
        )
        
        # Create RuntimeStack (depends on InfrastructureStack outputs)
        RuntimeStack(
            app,
            f"RuntimeStack-{stage}",
            stage=stage,
            vpc_id=infra_stack.vpc.vpc_id,
            ecr_repository_uri=infra_stack.ecr_repository.repository_uri,
            runtime_role_arn=infra_stack.runtime_role.role_arn,
            description=f"Runtime compute for Sales Agent - {stage} stage",
            env=env,
        )
    
    app.synth()


if __name__ == "__main__":
    main()
