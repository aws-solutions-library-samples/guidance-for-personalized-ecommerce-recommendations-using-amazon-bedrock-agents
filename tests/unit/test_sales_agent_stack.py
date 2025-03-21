import aws_cdk as core
import aws_cdk.assertions as assertions

from sales_agent.sales_agent_stack import salesAgentStack

# example tests. To run these tests, uncomment this file along with the example
# resource in sales_agent/sales_agent_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = salesAgentStack(app, "sales-agent")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
