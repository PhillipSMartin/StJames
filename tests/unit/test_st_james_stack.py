import aws_cdk as core
import aws_cdk.assertions as assertions

from src.st_james_stack import StJamesStack

# example tests. To run these tests, uncomment this file along with the example
# resource in st_james/st_james_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = StJamesStack(app, "st-james")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
