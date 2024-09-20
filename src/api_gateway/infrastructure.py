from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk.aws_lambda import Function
from constructs import Construct

class StJamesApiGateway(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        post_events_handler = kwargs['post_events_handler']
        self.testApi = apigw.LambdaRestApi(
            self, 'StJamesEventsApi',
            handler=post_events_handler,
            proxy=False
        )

        self.testApi.root.add_resource('post-events').add_method('POST') 