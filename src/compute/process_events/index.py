import boto3
import datetime
import json
import os

from boto3.dynamodb.conditions import Key

def handler(event, context):
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['TABLE_NAME'])

        # Get today's date in yyyy-mm-dd format
        today = datetime.date.today().isoformat()

        # Query items with date greater than today
        response = table.query(
            KeyConditionExpression=Key('access').eq('public') & Key('date_id').gt(today)
        )

        count = 0
        for item in response['Items']:
            if 'post' in item and isinstance(item['post'], list) and item['post']:
                print(f"Processing: {item['title']}: post={item['post']}")

                # Post messages to SNS topic
                post_to_sns(item)
                count += 1
                if count >= 3:
                    break
                
        return {
            'statusCode': 200,
            'body': 'Processing completed successfully'
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
    
    
def post_to_sns(item):
    # Initialize SNS client
    sns = boto3.client('sns')
    
    # Get the SNS topic ARN from environment variable
    topic_arn = os.environ['TOPIC_ARN']  
    
    # Publish the message to the SNS topic
    if 'version' in item:
        del item['version']
        
    response = sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(item),
        Subject=f"New post: {item.get('title', 'Untitled')}"
    )
    
    print(f"Message published to SNS. MessageId: {response['MessageId']}")
