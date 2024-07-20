from aws_cdk import (
    Fn,
    aws_lambda as lambda_,
    CfnOutput,
    custom_resources as cr,
    Stack
)
from constructs import Construct
from src.database.infrastructure import StJamesDatabase
import json

class StJamesStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        database = StJamesDatabase(self, "StJamesDatabase", tags={'Project': 'StJames'})

        with open('data/calendar.json', 'r') as file:
            calendar_data = json.load(file)

        # Create a Lambda function to insert the data
        initialize_events = lambda_.Function(
            self, 'InitializeEventsLambda',
            name='StJames-initialize-events',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/lambda/initialize_events'),
            environment={
                'TABLE_NAME': database.eventTable.table_name,
                'CALENDAR_DATA': json.dumps(calendar_data)

            },
            tags={'Project': 'StJames'}
        )

        # Grant the Lambda function write permissions to the table
        database.eventTable.grant_write_data(initialize_events)

        # Use a Custom Resource to run the Lambda function if the table did not previously exist
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
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE

            ),
            tags={'Project': 'StJames'}
        )

        # Output the table name

        CfnOutput(self, "StJamesEventTableName", value=database.eventTable.table_name)

        # Add tags to all resources in the stack
        for child in self.node.children:
            if hasattr(child, 'tags'):
                child.tags.set_tag('Project', 'StJames')