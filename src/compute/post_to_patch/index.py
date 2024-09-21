import boto3
import json
import os

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

def handler(event, context):

    events_posted = 0
    events_failed = 0

    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['TABLE_NAME'])

        for record in event["Records"]:
            posted = False
            try:
                message = json.loads(record["Sns"]["Message"])
                print("Request:", json.dumps(message))

                if update_status(table, message, 'posting'):

                    # TODO: Post to Patch

                    posted = True
                    print(f"Posted: { message['title'] }")

            except Exception as e:
                print(f"Failed to post: { message['title'] }")
                print(e)

            if posted:
                events_posted += 1
                update_status(table, message, 'posted')
            else:
                events_failed += 1
                update_status(table, message, 'post')

        body = f"Posted {events_posted} events, failed to post {events_failed} events"
        print(body)

        return {
            'statusCode': 200,
            'body': json.dumps({ 'message': body })
        }
                       
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({ 'message': 'Invalid JSON in event' })
        }
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({ 'message': 'Internal error' })
        }

# Update DynamoDB record with status
def update_status(table, message, status): 
    updated = False
    retry = True
    retry_count = 0

    try:       
        print( f"Updating { message['title'] } to { status }" )
        while retry and retry_count < 10: 
            retry = False
            retry_count += 1

            response = table.query(
                KeyConditionExpression=Key('access').eq('public') & Key('date_id').eq(message["date_id"])
            )

            if response['Items']:
                item = response['Items'][0]
                current_version = int( item.get('version', 0) )

                if 'post' in item and isinstance(item['post'], list) and 'patch' in item['post']:
                   item['post'].remove('patch')
                if 'posting' in item and isinstance(item['posting'], list) and 'patch' in item['posting']:
                   item['posting'].remove('patch')

                if status not in item:
                    item[status] = []
                item[status].append('patch') 

                try:
                    table.put_item(Item={
                            **item,
                            'version': current_version + 1
                        },
                        ConditionExpression='attribute_not_exists(version) OR version = :current_version',
                        ExpressionAttributeValues={':current_version': current_version}
                    ) 
                    updated = True

                except ClientError as e:
                    if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                        print(f"Conflict detected on attempt {retry_count}. Retrying...")
                        retry = True
                    else:
                        raise

    except Exception as e:
        print(f"Error updating status: {e}")

    if updated:
        print(f"Successfully updated { message['title'] } to { status }")
    else:
        print(f"Failed to update { message['title'] } to { status }")
    
    return updated