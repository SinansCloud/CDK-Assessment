import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk_assessment.cdk_assessment_stack import CdkAssessmentStack

# example tests. To run these tests, uncomment this file along with the example
# resource in cdk_assessment/cdk_assessment_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CdkAssessmentStack(app, "cdk-assessment")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
