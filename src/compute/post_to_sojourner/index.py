import boto3
import json
import os
import pytz
import re
import requests

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from datetime import datetime

website = 'sojourner'

current_item = None
current_status = None
current_version = 0

url = os.getenv('URL')

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
                    form_values = get_form_values()
                    if form_values and post_to_website(message, form_values):
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
                if current_status == 'posting':
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

def decode_captcha(e):
    result = ""
    for i in range(0, len(e), 2):
        hex_value = e[i : i + 2]
        char_code = int(hex_value, 16) + 1
        result += chr(char_code)
    return result

def get_form_values():
    # Perform an HTTP GET request
    response = requests.get(url)
    cookies = response.cookies
    
    # Check if the request was successful
    if response.status_code != 200:
         print(f"Request failed with status code {response.status_code}")
         return None
    
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract the hidden input fields for hs_fv_hash, hs_fv_ip, and hs_fv_timestamp
    hs_fv_hash = soup.find('input', {'name': 'hs_fv_hash'})['value']
    hs_fv_ip = soup.find('input', {'name': 'hs_fv_ip'})['value']
    hs_fv_timestamp = soup.find('input', {'name': 'hs_fv_timestamp'})['value']
    access_token = soup.find('input', {'name': '_token'})['value']

    # Extract the script tag containing the function definition
    script_tag = soup.find('script', text=re.compile(r"\w+\('\w+'\);"))
    
    if script_tag and script_tag.string:
        # Use regex to find the value passed to the function
        pattern = re.compile(r"\w+\('([0-9a-fA-F]+)'\);")
        match = pattern.search(script_tag.string)
        
        if match:
            passed_value = match.group(1)
            captcha_value = decode_captcha(passed_value)
        else:
            print("Captcha value not found in response")
            return None
    else:
        print("Script tag containing captcha function not found in response")
        return None
    
    # Return the extracted values as a dictionary    
    form_values = {
        'hs_fv_hash': hs_fv_hash,
        'hs_fv_ip': hs_fv_ip,
        'hs_fv_timestamp': hs_fv_timestamp,
        '_token': access_token,
        'captcha_value': captcha_value,
        'cookies': cookies
    }
    print(form_values)
    return form_values

def post_to_website(message, form_values):    
    date_str = message['date_id'].split('#')[0]
    date_and_time = date_str + ' ' + message['time']
    epoch_time = eastern_to_epoch(date_str, message['time'])
    secret = get_secret()

    payload = {
        "Custom12": "Yes",
        "Custom14": "All ages",
        "Custom15": "Scarsdale",
        "Custom16": "10 Church Lane",
        "Custom17": "NY",
        "Custom19": "",
        "Custom20": "",
        "Custom21": "",
        "Custom3": message['title'],
        "Custom4": message['description'],
        "Custom5": date_and_time,
        "Custom8": "Church of St. James the Less",
        "Custom9": "",
        "_token": form_values['_token'],
        "additional": "",
        "captcha": form_values['captcha_value'],  
        "doc[]": "",
        "fullname": "Phillip Martin",
        "hs_fv_hash": form_values['hs_fv_hash'],
        "hs_fv_ip": form_values['hs_fv_ip'],
        "hs_fv_timestamp": form_values['hs_fv_timestamp'],
        "required": "sEmail,fullname",
        "sEmail": secret["username"],
        "simple": "",
        "submit": "Submit Request",
        "xCategory": "8"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
       # "Cookie": f"JSESSIONID={access_token}"
    }

    print(f"Payload: { payload }")
    print(f"Headers: { headers }")
    response = requests.post(url, data=payload, headers=headers, cookies=form_values['cookies'])
    
    if response.status_code == 200:
        print("Post successful")
        return True
    
    else:
        print(f"Post failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False

