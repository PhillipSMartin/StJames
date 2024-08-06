import boto3
import datetime
import json
import requests
import os

from boto3.dynamodb.conditions import Key
from bs4 import BeautifulSoup

logged_in_to_gov = False
gov_signin_url = os.environ['GOV_SIGNIN_URL']   
gov_singin_id = os.environ['GOV_SIGNIN_ID']
gov_signin_password = os.environ['GOV_SIGNIN_PASSWORD']

def process_moms():
    # Stub function that currently returns False
    return False

def log_in_to_gov():
    response = requests.get(gov_signin_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', {'type': 'application/json', 'class': 'joomla-script-options new'})
        if script_tag:
            json_data = json.loads(script_tag.string)
            csrf_token = json_data['csrf.token']
            print(f'CSRF Token: {csrf_token}')
        else:
            print('CSRF token not found.')

    return True

def process_gov():
    global logged_in_to_gov
    if not logged_in_to_gov:
        logged_in_to_gov = log_in_to_gov()

    if logged_in_to_gov:
        # Stub function that currently returns False
        return False
    else:
        return False

def process_sojourner():
    # Stub function that currently returns False
    return False

def process_patch():
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
        result = process_moms()
        print(f"process_moms returned: {result}")

        if result:
            move_to_posted(item, 'moms')
            modified = True

    if 'gov' in item['post']:
        result = process_gov()
        print(f"process_gov returned: {result}")

        if result:
            move_to_posted(item, 'gov')
            modified = True

    if 'sojourner' in item['post']:
        result = process_sojourner()
        print(f"process_sojourner returned: {result}")

        if result:
            move_to_posted(item, 'sojourner')
            modified = True

    if 'patch' in item['post']:
        result = process_patch()
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
