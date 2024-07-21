from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    custom_resources as cr,
    Duration
)
from constructs import Construct

class StJamesLambda(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        eventTable = kwargs['eventTable']
        dataBucket = kwargs['dataBucket']
        initialEvents = kwargs['initialEvents']

       # Create a Lambda function to initialize the Events Table if it is empty
        initialize_events = lambda_.Function(
            self, 'InitializeEventsLambda',
            function_name='StJames-initialize-events',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/lambda_/initialize_events'),
            environment={
                'TABLE_NAME': eventTable.table_name,
                'BUCKET_NAME': dataBucket.bucket_name,
                'FILE_KEY': initialEvents
            },
            timeout=Duration.seconds(30),
        )

        # Grant the Lambda function write permissions to the table
        eventTable.grant_read_write_data(initialize_events)
        dataBucket.grant_read(initialize_events)

        # Use a Custom Resource to run the Lambda function 
        custom_resource_role = iam.Role(
            self, 'InitializeEventsCustomResourceRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ]
        )
        initialize_events.grant_invoke(custom_resource_role)

        cr.AwsCustomResource(
            self, 'InitializeEventsCustomResource',
            on_create=cr.AwsSdkCall(
                service='Lambda',
                action='invoke',
                physical_resource_id=cr.PhysicalResourceId.of('InitializeEventsCustomResource'),
                parameters={
                    'FunctionName': initialize_events.function_name
                }
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=['lambda:InvokeFunction'],
                    resources=[initialize_events.function_arn]
                )
            ]),
            role=custom_resource_role
        )

