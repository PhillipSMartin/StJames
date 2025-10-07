import boto3
import datetime
import json
import os, time, random

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


def inter_item_delay():
    """
    Sleep a small amount between items to reduce write contention.
    Controlled by env vars:
      DELAY_MS: base delay in milliseconds (default 250)
      JITTER_MS: max random jitter to add (default 150)
    """
    base = int(os.getenv("DELAY_MS", "250"))
    jitter = int(os.getenv("JITTER_MS", "150"))
    sleep_ms = base + random.randint(0, jitter)
    time.sleep(sleep_ms / 1000.0)


def handler(event, context):
    try:
        # Called by DynamoDB stream
        if 'Records' in event:
            print("Processing DynamoDB stream")
            process_dynamodb_stream(event)

        # Called by API Gateway
        else:
            print("Processing API call")
            process_api_call(event)
    
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON'})
        }
    
    except ClientError as e:
        print(f"AWS service error: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'AWS service error', 'error': e.response['Error']['Code']})
        }
    
    except KeyError as e:
        print(f"Missing key in data structure: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing required data'})
        }
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'})
        }
    
    return {
        'statusCode': 200,
        'body': 'Processing completed successfully'
    }   

def process_dynamodb_stream(event):
    processed_count = 0
    for record in event['Records']:
        if record['eventName'] == 'INSERT':
            item = convert_dynamodb_item(record['dynamodb']['NewImage'])
            print(f"Processing: {item['title']}: post={item['post']}")

            if post_to_sns(item):
                processed_count += 1
                inter_item_delay()  # ← add delay after each successful publish

    print(f"Processed {processed_count} table inserts")

def convert_dynamodb_item(item):
    def convert_value(value):
        if isinstance(value, dict):
            if 'S' in value:
                return value['S']
            elif 'N' in value:
                return int(value['N']) if value['N'].isdigit() else float(value['N'])
            elif 'BOOL' in value:
                return value['BOOL']
            elif 'L' in value:
                return [convert_value(v) for v in value['L']]
            elif 'M' in value:
                return convert_dynamodb_item(value['M'])
        return value

    return {k: convert_value(v) for k, v in item.items()}


def process_api_call(event):
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['TABLE_NAME'])

        today = datetime.date.today().isoformat()

        response = table.query(
            KeyConditionExpression=Key('access').eq('public') & Key('date_id').gt(today)
        )

        processed_count = 0
        items = response.get('Items', [])

        for idx, item in enumerate(items, start=1):
            if 'post' in item and isinstance(item['post'], list) and item['post']:
                print(f"Processing: {item['title']}: post={item['post']}")

                if post_to_sns(item):
                    processed_count += 1
                    # optional: skip the sleep after the last item to shave a little time
                    if idx < len(items):
                        inter_item_delay()

        print(f"Processed {processed_count} items")

    except ClientError as e:
        print(f"DynamoDB error: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise

    except KeyError as e:
        print(f"Missing environment variable: {e}")
        raise  

def post_to_sns(item):
    # Initialize SNS client
    sns = boto3.client('sns')
    
    # Get the SNS topic ARN from environment variable
    topic_arn = os.environ['TOPIC_ARN']  
    
    # Publish the message to the SNS topic
    if 'version' in item:
        del item['version']
        
    message = json.dumps(item)
    subject = f"New post: {item.get('title', 'Untitled')}"[:100]
    
    try:
        response = sns.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=subject
        )
        print(f"Message published to SNS. MessageId: {response['MessageId']}")
        return True

    except ClientError as e:
        print(f"Failed to publish message to SNS. Error code: {e.response['Error']['Code']}, Message: {e.response['Error']['Code']}")
        return False
    
    except KeyError as e:
        print(f"Missing key in item or environment variable: {e}")
        raise
