from aws_cdk import (
    CfnOutput,
    Stack,
    Tags
)
from constructs import Construct
from src.api.infrastructure import StJamesApi
from src.database.infrastructure import StJamesDatabase
from src.compute.infrastructure import StJamesCompute, StJamesLambdaTest
from src.messaging.infrastructure import StJamesMessaging
from src.storage.infrastructure import StJamesStorage

class StJamesStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Add a tag to the stack
        Tags.of(self).add('Project', 'StJames')

        # Create the DynamoDB tables
        database = StJamesDatabase(self, "StJamesDatabase")

        # Create the S3 bucket
        storage = StJamesStorage(self, "StJamesStorage")

        # Create the Lambda function for testing
        lambda_test = StJamesLambdaTest(self, "StJamesLambdaTest")
                                        
        # Create the API Gateway
        api = StJamesApi(self, "StJamesApiGateway",
            post_events_handler = lambda_test.post_tester)
        
        # Create the SNS topic
        messaging = StJamesMessaging(self, "StJamesMessaging")
        
        # Create the Lambda functions
        StJamesCompute(self, "StJamesLambdaProd",
            eventTable = database.events_table,
            dataBucket = storage.data_bucket,
            initialEvents = "initialData/events.json",
            testUrl = api.events_api.url)

        # Output the Events Table name
        CfnOutput(self, "EventTableName", 
            value=database.events_table.table_name,
            export_name="StJamesEventTableName")
