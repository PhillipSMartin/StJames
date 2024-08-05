from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    RemovalPolicy
)
from constructs import Construct

class StJamesStorage(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        self.dataBucket = s3.Bucket.from_bucket_name(
            self, "StJamesData",
            bucket_name="stjames-data-pm186"
        )

        # # Create an S3 bucket to hold data
        # self.dataBucket = s3.Bucket(self, "StJamesData",
        #     bucket_name="stjames-data-pm186",
        #     removal_policy=RemovalPolicy.DESTROY)
        
        # # Copy data to the S3 bucket to initialize the Events Table
        # s3deploy.BucketDeployment(self, "StJamesDataDeployment",
        #     sources=[s3deploy.Source.asset('data')],
        #     destination_bucket=self.dataBucket,
        #     destination_key_prefix='initialData')