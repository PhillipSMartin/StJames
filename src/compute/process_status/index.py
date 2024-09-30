import boto3
import json
import os

from botocore.exceptions import ClientError
 

def handler(event, context):

    try:
        print(f"Request parameters: {event['queryStringParameters']}")

        sort_key = event['queryStringParameters'].get('sort-key')
        new_status = event['queryStringParameters'].get('new-status')
        website = event['queryStringParameters'].get('website')
        error_message = None

        if (not new_status) or  (not sort_key) or (not website):
            error_message = 'key, new-status, and website parameters are required'

        if not error_message:
            old_status = event['queryStringParameters'].get('old-status')

            # Initialize DynamoDB client
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(os.environ['TABLE_NAME'])

            # Get the item and make sure current status is correct
            item, current_status, error_message = get_item_and_status(table, sort_key, website)
        
        if not error_message:           
            if old_status and current_status != old_status:
                error_message = f"Current status is not {old_status}"

        if not error_message:    
            error_message = update_status(table, item, website, new_status)

        if error_message:
            print(error_message)
            return {
                    'statusCode': 400,
                    'body': json.dumps({'message': error_message})
            }           
        else:
            msg = f"Successfully updated status of {sort_key} from {current_status} to {new_status} for {website}"
            print(msg)
            return {
                'statusCode': 200,
                'body': json.dumps({'message': msg})    
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error', 'error': str(e)})
        }
        
def get_item_and_status(table, sort_key, website):
    try:
        response = table.get_item(
            Key={
                'access': 'public',
                'date_id': sort_key
            },
            ConsistentRead=True
        )

        # get item
        item = response.get('Item', None)
        if not item:
            return None, f"No item found for { sort_key }"
        
        # get current status
        status_mapping = {
            'post': item.get('post', []),
            'posting': item.get('posting', []),
            'posted': item.get('posted', [])
        }

        current_status = next((status for status, websites in status_mapping.items() if website in websites), None)      
        return item, current_status, None
    
    except ClientError as e:
        return None, None, f"DynamoDB error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"

    except Exception as e:
        return None, None, f"Error getting item and status: {e}"

# Update DynamoDB record status
def update_status(table, item, website, new_status): 
    try:      
        # clear status
        status_keys = ['post', 'posting', 'posted']
        for key in status_keys:
            if key in item and isinstance(item[key], list):
                item[key] = [w for w in item[key] if w != website]

        # add the new status
        if new_status not in item:
            item[new_status] = []
        item[new_status].append(website) 

        table.put_item(Item={
                **item
            }
         ) 

    except ClientError as e:
        return None, None, f"DynamoDB error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"

    except Exception as e:
        return None, None, f"Error getting item and status: {e}"
