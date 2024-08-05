from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    CfnOutput,
    RemovalPolicy,
    Stack
)
from constructs import Construct
from src.database.infrastructure import StJamesDatabase
from src.lambda_.infrastructure import StJamesLambda
from src.storage.infrastructure import StJamesStorage

class StJamesStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the DynamoDB tables
        database = StJamesDatabase(self, "StJamesDatabase")

        # Create and fill the S3 buckets (don't need this - already done)
        storage = StJamesStorage(self, "StJamesStorage")

        # Create the Lambda functions
        StJamesLambda(self, "StJamesLambda",
            eventTable = database.eventsTable,
            dataBucket = storage.dataBucket,
            initialEvents = "initialData/events.json")

         # Output the Events Table name
        CfnOutput(self, "StJamesEventTableName", value=database.eventsTable.table_name)

        # Add tags to all resources in the stack
        for child in self.node.children:
            if hasattr(child, 'tags'):
                child.tags.set_tag('Project', 'StJames')