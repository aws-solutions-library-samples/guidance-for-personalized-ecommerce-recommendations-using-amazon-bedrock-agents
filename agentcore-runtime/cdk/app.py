#!/usr/bin/env python3
"""CDK app entry point for AgentCore Sales Agent infrastructure."""

import aws_cdk as cdk

from cdk.agentcore_stack import AgentCoreStack

app = cdk.App()
AgentCoreStack(app, "AgentCoreStack")
app.synth()
