import boto3
import json
import os
# import requests

from botocore.exceptions import ClientError

website = 'test'
error = None

sns = boto3.client('sns')
topic_arn = os.environ['TOPIC_ARN']  

def handler(event, context):
    global error

    events_posted = 0
    events_failed = 0

    try:
        for record in event["Records"]:

            item = json.loads(record["Sns"]["Message"])
            print("Request:", json.dumps(item))

            if not update_status(item, 'posting'):
                events_failed += 1
                post_to_sns(False, item)
                continue

            if post_to_website(item):
                events_posted += 1
                print(f"Posted: { item['title'] }")
                update_status(item, 'posted')
                post_to_sns(True, item)

            else:
                update_status(item, 'failed')
                post_to_sns(False, item)

        body = f"Posted {events_posted} events, failed to post {events_failed} events"
        print(body)

        return {
            'statusCode': 200,
            'body': json.dumps({ 'message': body })
        }
                    
    except json.JSONDecodeError as e:
        error = f"Error decoding JSON: {e}"
        print(error)
        post_to_sns(False)       
        return {
            'statusCode': 400,
            'body': json.dumps({ 'message': 'Invalid JSON in event' })
        }
    
    except Exception as e:
        error = f"Unexpected error: {e}"
        print(error)
        post_to_sns(False)
        return {
            'statusCode': 500,
            'body': json.dumps({ 'message': 'Internal error' })
        }
    
def post_to_sns(success, item=None): 
    try:      
        sns.publish(
            TopicArn=topic_arn,
            Message=error or 'No errors',
            Subject=f"Post to {website} {'succeeded' if success else 'failed'}: { item['title'] if item is not None else '' }"
        )
    except Exception as e:
        print(f"Failed to post to SNS: {e}")

def update_status(item, new_status):
    return True       
 
def post_to_website(item):    
    print (f'Posting {item["title"]}')
    return True        


