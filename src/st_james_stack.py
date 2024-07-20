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

        database = StJamesDatabase(self, "StJamesDatabase")

        with open('data/calendar.json', 'r') as file:
            calendar_data = json.load(file)

        # Create a Lambda function to insert the data
        insert_data_lambda = lambda_.Function(
            self, 'InsertDataLambda',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/lambda/insert_events'),
            environment={
                'TABLE_NAME': database.eventTable.table_name,
                'CALENDAR_DATA': json.dumps(calendar_data)
            }
        )

        # Grant the Lambda function write permissions to the table
        database.eventTable.grant_write_data(insert_data_lambda)

        # Use a Custom Resource to run the Lambda function if the table did not previously exist
        insert_data_resource = cr.AwsCustomResource(
            self, 'InsertDataCustomResource',
            #type="Custom::MyCustomResource",
            on_create=cr.AwsSdkCall(
                service='Lambda',
                action='invoke',
                physical_resource_id=cr.PhysicalResourceId.of('InsertDataCustomResource'),
                parameters={
                    'FunctionName': insert_data_lambda.function_name
                }
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            )
        )

        # Output the table name
        CfnOutput(self, "EventTableName", value=database.eventTable.table_name)