from aws_cdk import (
    RemovalPolicy,
    aws_dynamodb as db
)
from constructs import Construct

class StJamesDatabase(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        # Create the DynamoDB table to hold events
        self.events_table = db.Table(
            self, "EventsTable",
            table_name="StJamesEvents",
            partition_key=db.Attribute(name="access", type=db.AttributeType.STRING),
            sort_key=db.Attribute(name="date_id", type=db.AttributeType.STRING),
            removal_policy=RemovalPolicy.RETAIN,
            billing_mode=db.BillingMode.PAY_PER_REQUEST,
            stream=db.StreamViewType.NEW_AND_OLD_IMAGES
        )
