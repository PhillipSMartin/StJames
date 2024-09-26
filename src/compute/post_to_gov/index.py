import boto3
import json
import os
import requests

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from datetime import datetime

website = 'gov'
cookies = None

current_item = None
current_status = None
current_version = 0

login_url = os.getenv('LOGIN_URL')
post_url = os.getenv('POST_URL')
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

        if login_to_website():
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

def calculate_week_and_julian(date_string):
    # Parse the input date string
    date = datetime.strptime(date_string, "%m/%d/%Y")
    
    # Calculate the week number
    week_number = date.isocalendar()[1]
    
    # Calculate the Julian date
    julian_date = date.timetuple().tm_yday
    
    return week_number, julian_date

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
    global cookies

    secret = get_secret()

    response = requests.get(login_url)
    if response.status_code == 200:
        cookies = response.cookies
        print(f'Cookies: {cookies}')

        csrf_token = None
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', {'type': 'application/json', 'class': 'joomla-script-options new'})
 
        if script_tag:       
            json_data = json.loads(script_tag.string)
            csrf_token = json_data.get('csrf.token')
            print(f'CSRF Token: {csrf_token}')

        if not csrf_token:
            print('CSRF token not found.')
            return False  
         
        payload = {
            'Submit': '',
            csrf_token: '1',  # CSRF token
            'option': 'com_users',
            'password': secret['password'],
            'return': 'aW5kZXgucGhwp0I0ZW1pZD0xMTc=',
            'task': 'user.login',
            'username': secret['username']
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Send the POST request
        response = requests.post(login_url, data=payload, headers=headers)
        if response.status_code == 200:
            cookies = response.cookies
            print(f'Cookies: {cookies}')
            print(f'Login successful')
            return True
    
    print(f'Login failed: status code {response.status_code}')
    print(response.text)
    return False


def post_to_website(message):   
    return False 
    date_str = message['date_id'].split('#')[0]


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

    response = requests.post(post_url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print("Post successful")
        return True
    
    else:
        print(f"Post failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False
        


