from aws_cdk import (
    CfnOutput,
    Stack,
    Tags
)
from constructs import Construct
from src.api.infrastructure import StJamesApi
from src.database.infrastructure import StJamesDatabase
from src.compute.infrastructure import StJamesCompute
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
                                        
        
        # Create the SNS topic
        messaging = StJamesMessaging(self, "StJamesMessaging")
        
        # Create the Lambda functions
        compute = StJamesCompute(self, "StJamesLambdaProd",
            events_table = database.events_table,
            events_topic = messaging.events_topic,
            post_results_topic = messaging.post_results_topic,
            data_bucket = storage.data_bucket,
            initial_events = "initialData/events.json")
        
        # Create the API Gateway
        api = StJamesApi(self, "StJamesApiGateway",
            post_events_handler = compute.process_events)

        # Output the Events Table name
        CfnOutput(self, "EventTableName", 
            value=database.events_table.table_name,
            export_name="StJamesEventTableName")
