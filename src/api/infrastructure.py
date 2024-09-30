from aws_cdk import (
    aws_apigateway as apigw,
)
from constructs import Construct

class StJamesApi(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        self.events_api = apigw.RestApi(
            self, 'EventsApi',
            rest_api_name='StJames Events Api'
        )


class StJamesApiResources(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        api = kwargs['api']
        post_events_handler = kwargs['post_events_handler']
        status_handler = kwargs['status_handler']

        post_events = api.events_api.root.add_resource('post-events')
        post_events_integration = apigw.LambdaIntegration(post_events_handler)
        post_events.add_method('POST', post_events_integration)

        status = api.events_api.root.add_resource('status')
        status_integration = apigw.LambdaIntegration(status_handler)
        status.add_method('POST', status_integration, 
            request_parameters={
                'method.request.querystring.old-status': False,  # Optional
                'method.request.querystring.new-status': True,   # Required
            }
        )

