from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    Duration
)
from constructs import Construct

class StJamesCompute(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        events_table = kwargs['events_table']
        events_topic = kwargs['events_topic']
        data_bucket = kwargs['data_bucket']
        initial_events = kwargs['initial_events']

       # Create a Lambda function to initialize the Events Table if it is empty
        self.initialize_events = lambda_.Function(
            self, 'InitializeEventsLambda',
            function_name='StJames-initialize-events',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/compute/initialize_events'),
            environment={
                'TABLE_NAME': events_table.table_name,
                'BUCKET_NAME': data_bucket.bucket_name,
                'FILE_KEY': initial_events
            },
            timeout=Duration.seconds(30),
        )

        # Grant the Lambda function necessary permissions
        events_table.grant_read_write_data(self.initialize_events)
        data_bucket.grant_read(self.initialize_events)


        # Create a Lambda function to process the Events Table
        self.process_events = lambda_.Function(
            self, 'ProcessEventsLambda',
            function_name='StJames-process-events',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/compute/process_events'),
            environment={
                'TABLE_NAME': events_table.table_name,
                'TOPIC_ARN': events_topic.topic_arn
            },
            timeout=Duration.seconds(30),
        )

        # Grant the Lambda function necessary permissions
        events_table.grant_read_data(self.process_events)
        events_topic.grant_publish(self.process_events)

        # Create a Lambda function to post to the patch site
        self.post_to_patch = lambda_.Function(
            self, 'PostToPatchLambda',
            function_name='StJames-post-to-patch',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/compute/post_to_patch'),
            environment={
                'TABLE_NAME': events_table.table_name
            },
            timeout=Duration.seconds(10),
        )

        # Subscribe the post_to_patch Lambda to the events_topic
        events_topic.add_subscription(
            subscriptions.LambdaSubscription(
                self.post_to_patch,
                filter_policy_with_message_body={
                    'post': sns.FilterOrPolicy.filter(sns.SubscriptionFilter.string_filter(
                        allowlist=['patch']
                    ))
                }            
            )
        )

        # Grant the Lambda function necessary permissions
        events_table.grant_read_write_data(self.post_to_patch)

        # Create a Lambda function to post to the moms site
        self.post_to_moms = lambda_.Function(
            self, 'PostToMomsLambda',
            function_name='StJames-post-to-moms',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/compute/post_to_moms'),
            environment={
                'TABLE_NAME': events_table.table_name
            },
            timeout=Duration.seconds(10),
        )

        # Subscribe the post_to_moms Lambda to the events_topic
        events_topic.add_subscription(
            subscriptions.LambdaSubscription(
                self.post_to_moms,
                filter_policy_with_message_body={
                    'post': sns.FilterOrPolicy.filter(sns.SubscriptionFilter.string_filter(
                        allowlist=['moms']
                    ))
                }            
            )
        )

        # Grant the Lambda function necessary permissions
        events_table.grant_read_write_data(self.post_to_moms)

        # Create a Lambda function to post to the sojourner site
        self.post_to_sojourner = lambda_.Function(
            self, 'PostToSojournerLambda',
            function_name='StJames-post-to-sojourner',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('src/compute/post_to_sojourner'),
            environment={
                'TABLE_NAME': events_table.table_name
            },
            timeout=Duration.seconds(10),
        )

        # Subscribe the post_to_sojourner Lambda to the events_topic
        events_topic.add_subscription(
            subscriptions.LambdaSubscription(
                self.post_to_sojourner,
                filter_policy_with_message_body={
                    'post': sns.FilterOrPolicy.filter(sns.SubscriptionFilter.string_filter(
                        allowlist=['sojourner']
                    ))
                }            
            )
        )

        # Grant the Lambda function necessary permissions
        events_table.grant_read_write_data(self.post_to_sojourner)

        # # Create a Lambda function to post to the gov site
        # self.post_to_patch = lambda_.Function(
        #     self, 'PostToGovLambda',
        #     function_name='StJames-post-to-patch',
        #     runtime=lambda_.Runtime.PYTHON_3_9,
        #     handler='index.handler',
        #     code=lambda_.Code.from_asset('src/compute/post_to_gov'),
            # environment={
            #     'TABLE_NAME': events_table.table_name,
            #     'GOV_URL': 'https://events.westchestergov.com/event-calendar-sign-in',   
            #     'GOV_SIGNIN_ID'': 'camryni',
            #     'GOV_SIGNIN_PASSWORD': 'CamrynAdmin17',
            # },
        #     timeout=Duration.seconds(10),
        # )

        # # Subscribe the post_to_gov Lambda to the events_topic
        # events_topic.add_subscription(
        #     subscriptions.LambdaSubscription(
        #         self.post_to_gov,
        #         filter_policy_with_message_body={
        #             'post': sns.FilterOrPolicy.filter(sns.SubscriptionFilter.string_filter(
        #                 allowlist=['gov']
        #             ))
        #         }            
        #     )
        # )        

        # # Grant the Lambda function necessary permissions
        # events_table.grant_read_write_data(self.post_to_gov)