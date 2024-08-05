import boto3
import datetime
import os

from boto3.dynamodb.conditions import Key, Attr

def process_moms():
    # Stub function that currently returns False
    return False

def handler(event, context):
    # Initialize DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['TABLE_NAME'])

    # Get today's date in yyyy-mm-dd format
    today = datetime.date.today().isoformat()

    # Query items with date greater than today
    response = table.query(
        KeyConditionExpression=Key('access').eq('public') & Key('date_id').gt(today)
    )

    for item in response['Items']:
        print(f"Processing: {item['title']}")
        if 'post' in item and isinstance(item['post'], list):
            if 'moms' in item['post']:
                result = process_moms()
                print(f"process_moms returned: {result}")

                if result:
                    item['post'].remove('moms')
                    if 'posted' not in item:
                        item['posted'] = []
                    item['posted'].append('moms')

                    # Update the item in DynamoDB
                    table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': 'Processing completed successfully'
    }
