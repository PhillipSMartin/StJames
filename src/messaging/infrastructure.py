from aws_cdk import aws_sns as sns
from constructs import Construct

class StJamesMessaging(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        # Create an SNS topic
        self.events_topic = sns.Topic(
            self, "EventsTopic",
            topic_name="StJames-events-topic",
            display_name="St. James Events Topic"
        )
