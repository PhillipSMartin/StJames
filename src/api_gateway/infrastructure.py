from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk.aws_lambda import Function
from constructs import Construct

class StJamesApiGateway(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        post_tester = kwargs['post_tester']
        self.testApi = apigw.LambdaRestApi(
            self, 'StJamesTestApi',
            handler=post_tester,
            proxy=False
        )

        self.testApi.root.add_resource('test').add_method('POST') 