import boto3
import json
import os
import pytz
import requests

from datetime import datetime


from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

website = 'patch'
access_token = None

def handler(event, context):

    events_posted = 0
    events_failed = 0

    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['TABLE_NAME'])

        # if login_to_patch():

        for record in event["Records"]:
            posted = False
            try:
                message = json.loads(record["Sns"]["Message"])
                print("Request:", json.dumps(message))

                if update_status(table, message, 'posting'):

                    if post_to_patch(message):
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

    # for the time being, turn this off
    return True

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

                if 'post' in item and isinstance(item['post'], list) and website in item['post']:
                   item['post'].remove(website)
                if 'posting' in item and isinstance(item['posting'], list) and website in item['posting']:
                   item['posting'].remove(website)

                if status not in item:
                    item[status] = []
                item[status].append(website) 

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

def eastern_to_epoch(date_str, time_str):
    # Combine date and time strings
    datetime_str = f"{date_str} {time_str}"
    
    # Parse the datetime string
    dt = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")
    
    # Set the timezone to Eastern Time
    eastern = pytz.timezone('US/Eastern')
    dt_with_tz = eastern.localize(dt)
    
    # Convert to UTC
    utc_time = dt_with_tz.astimezone(pytz.UTC)
    
    # Convert to Unix epoch time
    epoch_time = int(utc_time.timestamp())
    
    return epoch_time


def login_to_patch():
    global access_token

    url = "https://pep.patchapi.io/api/authn/token"
    payload = {
        "username": "07_topper_sights@icloud.com",
        "password": "&g$DdCXPgj8A55G3"
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        access_token = data['data']['access_token']
        return True
    
    else:
        print(f"Failed to obtain access token. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return False

def post_to_patch(message):    
    date_str = message['date_id'].split('#')[0]
    epoch_time = eastern_to_epoch(date_str, message['time'])

    url = "https://api.patch.com/calendar/write-api/event"  
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

    return True
        


