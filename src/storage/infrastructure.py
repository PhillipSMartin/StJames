from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    RemovalPolicy
)
from constructs import Construct

class StJamesStorage(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        self.data_bucket = s3.Bucket.from_bucket_name(
            self, "DataBucket",
            bucket_name="stjames-data-pm186"
        )
        
        # # Copy data to the S3 bucket to initialize the Events Table
        # s3deploy.BucketDeployment(self, "StJamesDataDeployment",
        #     sources=[s3deploy.Source.asset('data')],
        #     destination_bucket=self.data_bucket,
        #     destination_key_prefix='initialData')