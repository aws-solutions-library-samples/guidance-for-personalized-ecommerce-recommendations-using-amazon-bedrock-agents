#!/usr/bin/env python3
"""CDK app entry point for AgentCore Sales Agent infrastructure."""

import aws_cdk as cdk

from cdk.agentcore_stack import AgentCoreStack

app = cdk.App()
env_name = app.node.try_get_context("env-name") or "production"
AgentCoreStack(app, f"AgentCoreStack-{env_name}", env_name=env_name)
app.synth()
