import boto3
import json
import os
import pytz
import requests

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime

website = 'patch'
access_token = None
sns = boto3.client('sns')

login_url = os.getenv('LOGIN_URL')
post_url = os.getenv('POST_URL')
topic_arn = os.environ['TOPIC_ARN']  
status_url = os.environ['STATUS_URL'] 

def handler(event, context):
    events_posted = 0
    events_failed = 0

    try:
        success, error_message = login_to_website()
        if not success:
            print(error_message)
            post_to_sns(False, None, error_message)
        
        else:
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
            'body': json.dumps({ 'message': body })
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
        title = item['title'] if item is not None else ''
        subject = f"Post to {website} {'succeeded' if success else 'failed'}: {title}"[:100]
        sns.publish(
            TopicArn=topic_arn,
            Message=error_message or 'No errors',
            Subject=subject
        )
    except Exception as e:
        print(f"Failed to post to SNS: {e}")

def update_status(item, new_status):
    try:
        print(f"Updating status of {item['title']} to {new_status}")
        params = {
            "sort-key": item["date_id"],
            "new-status": new_status,
            "website": website
        }
        if new_status == 'posting':
            params["old-status"] = "post"

        response = requests.post(status_url, params=params)       
        if response and response.status_code == 200:
            return True, None
        else:
            msg = (f"Failed to update status: {response.text if response else 'No response from api'}")
            print(msg)
            return False, msg
        
    except Exception as e:
        msg = f"Failed to update status: {e}"
        print(msg)
        return False, msg

def eastern_to_epoch(date_str, time_str):
    # Combine date and time strings
    datetime_str = f"{date_str} {time_str}"
    
    # Parse the datetime string
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")
    except Exception:
        dt = None
    
    if not dt:
        try:
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %I %p")
        except Exception:
                raise Exception(f"Failed to parse date and time")
    
    # Set the timezone to Eastern Time
    eastern = pytz.timezone('US/Eastern')
    dt_with_tz = eastern.localize(dt)
    
    # Convert to UTC
    utc_time = dt_with_tz.astimezone(pytz.UTC)
    
    # Convert to Unix epoch time
    epoch_time = int(utc_time.timestamp())
    
    return epoch_time

def get_secret():
    secret_name = os.environ.get('SECRET_NAME')
    region_name = os.environ.get('REGION_NAME')

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    secret = json.loads(get_secret_value_response['SecretString'])
    return secret


def login_to_website():
    try:
        global access_token
        
        secret = get_secret()
        payload = {
            "username": secret['username'],
            "password": secret['password']
        }
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(login_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data['data']['access_token']
            return True, None
        
        else:
            return False, f"Failed to obtain access token: status code={response.status_code}, number of cookies={len(session.cookies)}"

    except Exception as e:
        return False, f"Failed to obtain access token: {e}"

def post_to_website(message): 
    try:   
        date_str = message['date_id'].split('#')[0]
        epoch_time = eastern_to_epoch(date_str, message['time'])

        payload = {
            "eventDateEpoch": epoch_time,
            "eventType": "free",
            "title": message['title'],
            "contentHtml": f"<p>{ message['description'] }</p>",
            "patchId": "37",
            "eventAddress": {
                "country":"US",
                "state":"NY",
                "locality":"Scarsdale",
                "postalCode":"10583",
                "streetAddress":"10 Church Ln",
                "premise":"",
                "name":"The Church of St. James the Less"
            },
            "imageUrls": [
                "https://stjames-data-pm186.s3.amazonaws.com/SJL+logo.jpg"
            ],
            "eventLocation": {
                "type":"Point",
                "coordinates":[-73.8000084,40.98955369999999]
            },
            "imageValidation": [
                {
                    "image_filename": "SJL logo.jpg",
                    "image_src": "",
                    "image_suspect": 0,
                    "image_url": "https://stjames-data-pm186.s3.amazonaws.com/SJL+logo.jpg"
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Patch-Authorization": f"Bearer {access_token}"
        }

        print(f"Payload: { payload }")
        print(f"Headers: { headers }")
        
        if 'test' in message:
            print("Test mode - not posting")
            return True, None
        
        response = requests.post(post_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            print("Post successful")
            return True, None
        
        else:
            return False, f"Post failed with status code {response.status_code}: {response.text}"
        
    except Exception as e:
        return False, f"Error posting to website: {e}"
            


