import boto3
import json
import os
# import requests

from botocore.exceptions import ClientError

website = 'test'

sns = boto3.client('sns')
topic_arn = os.environ['TOPIC_ARN']  

def handler(event, context):
    error_message = None 
    events_posted = 0
    events_failed = 0

    try:
        for record in event["Records"]:

            # Retrieve info about event to post
            item = json.loads(record["Sns"]["Message"])
            print("Request:", json.dumps(item))

            # Set status to 'posting' to prevent duplicate posts
            # Currrent status should be 'post' - returns False if it isn't
            success, error_message = update_status(item, 'posting')
            if not success:
                events_failed += 1
                post_to_sns(False, item, error_message)
                continue

            # Post to website
            success, error_message = post_to_website(item)
            if success:
                events_posted += 1
                print(f"Posted: { item['title'] }")

                # Set status to 'posted'
                update_status(item, 'posted')
                post_to_sns(True, item)

            else:
                events_failed += 1
                print(f"Failed to post { item['title'] }: { error_message }")

                # Set status back to 'post' so we can try again after fixing the issue
                update_status(item, 'post')
                post_to_sns(False, item, error_message)

        body = f"Posted {events_posted} events, failed to post {events_failed} events"
        print(body)

        return {
            'statusCode': 200,
            'body': json.dumps({ 'error_message': body })
        }
                    
    except json.JSONDecodeError as e:
        error_message = f"Error decoding JSON: {e}"
        print(error_message)
        post_to_sns(False, None, error_message)
        return {
            'statusCode': 400,
            'body': json.dumps({ 'error_message': 'Invalid JSON in event' })
        }
    
    except Exception as e:
        error_message = f"Unexpected error: {e}"
        print(error_message)
        post_to_sns(False, None, error_message)
        return {
            'statusCode': 500,
            'body': json.dumps({ 'error_message': 'Internal error' })
        }
    
def post_to_sns(success, item, error_message=None): 
    try:      
        sns.publish(
            TopicArn=topic_arn,
            Message=error_message or 'No errors',
            Subject=f"Post to {website} {'succeeded' if success else 'failed'}: { item['title'] if item is not None else '' }"
        )
    except Exception as e:
        print(f"Failed to post to SNS: {e}")

def update_status(item, new_status):
    print(f"Updating status of {item['title']} to {new_status}")
    return False, "Testing error message handling"       
 
def post_to_website(item):    
    print (f'Posting {item["title"]} to {website}')
    return True, None        


