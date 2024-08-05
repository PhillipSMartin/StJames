import boto3
import datetime
import os

from boto3.dynamodb.conditions import Key, Attr

def process_moms():
    # Stub function that currently returns False
    return False

def process_gov():
    # Stub function that currently returns False
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
