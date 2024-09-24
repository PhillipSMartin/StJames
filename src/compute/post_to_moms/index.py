import boto3
import json
import os
import pytz
import requests

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime

website = 'moms'
access_token = None

current_item = None
current_status = None
current_version = 0

url = os.getenv('URL')
sns = boto3.client('sns')
topic_arn = os.environ['TOPIC_ARN']  
    
def handler(event, context):

    global current_item
    global current_status

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

                if not ( get_item(table, message) and current_status == 'post' ):
                    print( "Status of event is not 'post', skipping" )
                    events_failed += 1
                    continue

                if update_status(table, message, 'posting'):
                    if post_to_website(message):
                        posted = True
                        print(f"Posted: { message['title'] }")

            except Exception as e:
                print(f"Failed to post: { message['title'] }")
                print(e)

            if posted:
                events_posted += 1
                update_status(table, message, 'posted')
                post_to_sns(f"Posted to {website}: { message['title'] }")

            else:
                events_failed += 1
                if current_status == 'posting':
                    update_status(table, message, 'post')
                post_to_sns(f"Failed to post to {website}: { message['title'] }")

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

def post_to_sns(message): 
    try:      
        sns.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=f"Result from post_to_{website}"
        )
    except Exception as e:
        print(f"Failed to post to SNS: {e}")

# update item, status, and version
def get_item(table, message):
    global current_item
    global current_status
    global current_version

    response = table.get_item(
        Key={
            'access': 'public',
            'date_id': message['date_id']
        },
        ConsistentRead=True
    )

    current_item = response.get('Item', None)
    if not current_item:
        print(f"No item found for { message['title'] }")
        return False
    
    # save the current version and remove it from the item - wee will update the version later
    current_version = int(current_item.get('version', 0))
    if 'version' in current_item:
        del current_item['version']

    # save the current status
    if 'post' in current_item and isinstance(current_item['post'], list) and website in current_item['post']:
        current_status = 'post'
    elif 'posting' in current_item and isinstance(current_item['posting'], list) and website in current_item['posting']:
        current_status = 'posting'
    elif 'posted' in current_item and isinstance(current_item['posted'], list) and website in current_item['posted']:
        current_status = 'posted'
    else:
        print(f"No status found for { message['title'] }")
        return False
    
    return True

# Update DynamoDB record status
def update_status(table, message, new_status): 
    global current_item
    global current_status
    global current_version

    updated = False
    retry_count = 0

    try:       
        print( f"Updating { message['title'] } to { new_status }" )

        while retry_count < 10 and not updated: 
            retry_count += 1
 
            # clear status
            if 'post' in current_item and isinstance(current_item['post'], list) and website in current_item['post']:
                current_item['post'].remove(website)
            if 'posting' in current_item and isinstance(current_item['posting'], list) and website in current_item['posting']:
                current_item['posting'].remove(website)
            if 'posted' in current_item and isinstance(current_item['posted'], list) and website in current_item['posted']:
                current_item['posted'].remove(website)

            # add the new status
            if new_status not in current_item:
                current_item[new_status] = []
            current_item[new_status].append(website) 

            try:
                table.put_item(Item={
                        **current_item,
                        'version': current_version + 1
                    },
                    ConditionExpression='attribute_not_exists(version) OR version = :current_version',
                    ExpressionAttributeValues={':current_version': current_version}
                ) 
                updated = True
                current_version += 1
                current_status = new_status

            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    print(f"Conflict detected on attempt {retry_count}. Retrying...")
                    get_item( table, message )  
                else:
                    raise

    except Exception as e:
        print(f"Error updating status: {e}")

    if not updated:
        print(f"Failed to update { message['title'] } to { new_status }")
    
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

def post_to_website(message):    
    date_str = message['date_id'].split('#')[0]
    start_time = eastern_to_epoch(date_str, message['time']) * 1000
    end_time = start_time + 3600000
    secret = get_secret()

    payload = {
        "event": {
            "what": {
                "summary": message['title'],
                "description": f"<p>{message['description']}</p>",
                "image": {
            "url": "https://stjames-data-pm186.s3.amazonaws.com/SJL+logo.jpg",
                    "name": "user-image: SJL logo",
                    "width": 485,
                    "height": 247,
                    "altText": ""
                }
            },
            "where": {
                "place": "Church of St. James the Less",
                "address": "10 Church Lane, Scarsdale, NY 10583, USA",
                "location": {
                    "name": "10 Church Ln",
                    "place_id": "ChIJvX-hGnSTwokRK_iMMwfNni0",
                    "c_country": "United States",
                    "c_locality": "Scarsdale",
                    "c_postcode": "10583",
                    "c_region": "New York",
                    "c_street": "10 Church Lane",
                    "latitude": 40.9897687,
                    "longitude": -73.7999511
                },
                "virtualLoc": {}
            },
            "when": {
                "start": {
                    "millis": start_time,
                    "tzid": "America/New_York"
                },
                "end": {
                    "millis": end_time,
                    "tzid": "America/New_York"
                },
                "allDay": False
            },
            "emeta": {
                "tags": {
                    "default": []
                }
            }
        },
        "submitter": {
            "name": "Phillip Martin",
            "email": secret['username'],
            "notes": ""
        }
    }

    headers = {
        "Content-Type": "application/json",
    }

    print(f"Payload: { payload }")
    print(f"Headers: { headers }")

    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print("Post successful")
        return True
    
    else:
        print(f"Post failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False



