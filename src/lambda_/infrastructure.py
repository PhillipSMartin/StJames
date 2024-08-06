from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    Duration
)
from constructs import Construct

class StJamesLambda(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        eventTable = kwargs['eventTable']
        dataBucket = kwargs['dataBucket']
        initialEvents = kwargs['initialEvents']

       # Create a Lambda function to initialize the Events Table if it is empty
        initialize_events = lambda_.Function(
            self, 'InitializeEventsLambda',
            function_name='StJames-initialize-events',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/lambda_/initialize_events'),
            environment={
                'TABLE_NAME': eventTable.table_name,
                'BUCKET_NAME': dataBucket.bucket_name,
                'FILE_KEY': initialEvents
            },
            timeout=Duration.seconds(30),
        )

        # Grant the Lambda function read/write permissions to the table
        eventTable.grant_read_write_data(initialize_events)
        dataBucket.grant_read(initialize_events)

        # Create a Lambda function to process the Events Table
        process_events = lambda_.Function(
            self, 'ProcessEventsLambda',
            function_name='StJames-process-events',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/lambda_/process_events'),
            environment={
                'TABLE_NAME': eventTable.table_name,
                'GOV_SIGNIN_URL': 'https://events.westchestergov.com/event-calendar-sign-in',   
                'GOV_SIGNIN_ID': 'camryni',
                'GOV_SIGNIN_PASSWORD': 'CamrynAdmin17'
            },
            timeout=Duration.seconds(30),
        )

        # Grant the Lambda function read/write permissions to the table
        eventTable.grant_read_write_data(process_events)

        # Create a Lambda function to simulate the websites
        self.post_tester = lambda_.Function(
            self, 'TestPosterLambda',
            function_name='StJames-test-poster',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/lambda_/test_poster'),
            timeout=Duration.seconds(10),
        )
