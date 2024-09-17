import boto3
import datetime
import json
import requests
import os

from boto3.dynamodb.conditions import Key
from bs4 import BeautifulSoup

test_url = os.environ['TEST_URL']
gov_url = os.eviron['GOV_URL']
gov_signin_url = (test_url + 'test') if test_url else gov_url  
gov_signin_id = os.environ['GOV_SIGNIN_ID']
gov_signin_password = os.environ['GOV_SIGNIN_PASSWORD']

gov_login_status = 'not logged in'

def process_moms(item):
    # Stub function that currently returns False
    return False

def log_in_to_gov():
    response = requests.get(gov_url)
    if response.status_code == 200:
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
            'password': gov_signin_password,
            'return': 'aW5kZXgucGhwp0I0ZW1pZD0xMTc=',
            'task': 'user.login',
            'username': gov_signin_id
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Send the POST reqest
        response = requests.post(gov_url, data=payload, headers=headers)
        if response.status_code == 200:
            print(f'Logged in to {gov_url} successfully!')
            return True
        else:
            print(f'Failed to log in to {gov_url}: status code {response.status_code}')
            print(response.text)

    return False

def process_gov(item):
    global gov_login_status
    if gov_login_status == 'not logged in' and gov_login_status != 'failed':
        gov_login_status = 'logged in' if log_in_to_gov() else 'failed'

    if gov_login_status == 'logged in':
        payload = {
            'Submit': '',
            csrf_token: '1',  # CSRF token
            'option': 'com_users',
            'password': gov_signin_password,
            'return': 'aW5kZXgucGhwp0I0ZW1pZD0xMTc=',
            'task': 'user.login',
            'username': gov_signin_id
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        return False
    else:
        return False

def process_sojourner(item):
    # Stub function that currently returns False
    return False

def process_patch(item):
    # Stub function that currently returns False
    return False

def move_to_posted(item, website):
    item['post'].remove(website)
    if 'posted' not in item:
        item['posted'] = []
    item['posted'].append(website) 
    
def post_to_websites(item): 
    modified = False

    if 'moms' in item['post']:
        result = process_moms(item)
        print(f"process_moms returned: {result}")

        if result:
            move_to_posted(item, 'moms')
            modified = True

    if 'gov' in item['post']:
        result = process_gov(item)
        print(f"process_gov returned: {result}")

        if result:
            move_to_posted(item, 'gov')
            modified = True

    if 'sojourner' in item['post']:
        result = process_sojourner(item)
        print(f"process_sojourner returned: {result}")

        if result:
            move_to_posted(item, 'sojourner')
            modified = True

    if 'patch' in item['post']:
        result = process_patch(item)
        print(f"process_patch returned: {result}")
        
        if result:
            move_to_posted(item, 'patch')
            modified = True

    return modified


def handler(event, context):
    # Initialize DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['TABLE_NAME'])

    # Get today's date in yyyy-mm-dd format
    today = datetime.date.today().isoformat()

    # Query items with date greater than today
    response = table.query(
        KeyConditionExpression=Key('access').eq('public') & Key('date_id').gt(today)
    )

    for item in response['Items']:
        if 'post' in item and isinstance(item['post'], list):
            print(f"Processing: {item['title']}: post={item['post']}")

            if post_to_websites(item):
                # Update the item in DynamoDB
                print(f"Updating: {item['title']}: posted={item['posted']}")
                table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': 'Processing completed successfully'
    }
