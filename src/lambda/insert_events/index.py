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
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    calendar_data = json.loads(os.environ['CALENDAR_DATA'])

    if is_table_empty(table):
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
