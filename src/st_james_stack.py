from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    CfnOutput,
    Stack,
    Tags
)
from constructs import Construct
from src.api_gateway.infrastructure import StJamesApiGateway
from src.database.infrastructure import StJamesDatabase
from src.lambda_.infrastructure import StJamesLambdaProd, StJamesLambdaTest
from src.storage.infrastructure import StJamesStorage

class StJamesStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Add a tag to the stack
        Tags.of(self).add('Project', 'StJames')

        # Create the DynamoDB tables
        database = StJamesDatabase(self, "StJamesDatabase")

        # Create and fill the S3 buckets (don't need this - already done)
        storage = StJamesStorage(self, "StJamesStorage")

        # Create the Lambda function for testing
        lambda_test = StJamesLambdaTest(self, "StJamesLambdaTest")
                                        
        # Create the API Gateway for testing
        api = StJamesApiGateway(self, "StJamesApiGateway",
            post_tester = lambda_test.post_tester)
        
        # Create the Lambda functions
        StJamesLambdaProd(self, "StJamesLambdaProd",
            eventTable = database.eventsTable,
            dataBucket = storage.dataBucket,
            initialEvents = "initialData/events.json",
            testUrl = api.testApi.url)

        # Output the Events Table name
        CfnOutput(self, "EventTableName", 
            value=database.eventsTable.table_name,
            export_name="StJamesEventTableName")
