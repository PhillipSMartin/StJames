import boto3
import json
import os

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

def handler(event, context):
    try:
        message = json.loads(event["Records"][0]["Sns"]["Message"])
        print("Request:", json.dumps(message))

        status_code = 200
        body = f"Successfully posted: { message['title'] }"
        
        # Find DynamoDB record
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['TABLE_NAME'])

        retry = True
        retry_count = 0
        while retry and retry_count < 10: 
            retry = False
            response = table.query(
                KeyConditionExpression=Key('access').eq('public') & Key('date_id').eq(message['date_id'])
            )

            if response['Items']:
                item = response['Items'][0]
                current_version = item.get('version', 0)

                if 'post' in item and isinstance(item['post'], list) and 'patch' in item['post']:
                    print(f"Posting: {message['title']}")

                    item['post'].remove('patch')
                    if 'posted' not in item:
                        item['posted'] = []
                    item['posted'].append('patch') 

                    try:
                        table.put_item(Item={
                                **item,
                                'version': current_version + 1
                            },
                            ConditionExpression='attribute_not_exists(version) OR version = :current_version',
                            ExpressionAttributeValues={':current_version': current_version}
                        ) 
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                            retry = True
                            retry_count += 1
                        else:
                            raise
 
                else:
                    status_code = 400
                    body = f"Error: { item['title'] } - already posted"

            else:
                status_code = 400
                body = f"Error - not found: { message['date_id'] }"

        # If retry is True, we tried to mark the item as posted but failed.
        if retry:
            status_code = 500
            body = f"Error - unable to update DynamoDB table: { message['date_id'] }"
        
        print(body)
        return {
            'statusCode': status_code,
            'body': json.dumps({'message': body })
        }
                   
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON in event'})
        }
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'})
        }
