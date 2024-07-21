import json
import boto3
import os
import uuid

def is_table_empty(table):
    response = table.scan(
        Select='COUNT',
        Limit=1
    )
    return response['Count'] == 0

def handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    s3 = boto3.client('s3')

    table = dynamodb.Table(os.environ['TABLE_NAME'])
    bucket_name = os.environ['BUCKET_NAME']
    file_key = os.environ['FILE_KEY']

    if is_table_empty(table):
        # Get the data from the S3 bucket
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        calendar_data = json.loads(response['Body'].read().decode('utf-8'))

        # Insert the data into the DynamoDB table
        with table.batch_writer() as batch:
            for item in calendar_data:
                item['id'] = str(uuid.uuid4())  # Generate a unique ID for each item
                batch.put_item(Item=item)
        return {
            'statusCode': 200,
            'body': json.dumps('Data inserted successfully')
        }
    else:
        return {
            'statusCode': 200,
            'body': json.dumps('Table is not empty, no data inserted')
        }
