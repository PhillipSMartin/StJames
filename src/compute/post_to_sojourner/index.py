import boto3
import json
import os
import re
import requests

from botocore.exceptions import ClientError
from bs4 import BeautifulSoup

website = 'sojourner'
sns = boto3.client('sns')
url = os.getenv('URL')

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
                form_values, error_message = get_form_values()
                if not form_values:
                    success = False
                else: 
                    success, error_message = post_to_website(item, form_values)  

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
        sns.publish(
            TopicArn=topic_arn,
            Message=error_message or 'No errors',
            Subject=f"Post to {website} {'succeeded' if success else 'failed'}: { item['title'] if item is not None else '' }"
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
    try:
        # Perform an HTTP GET request
        response = requests.get(url)
        cookies = response.cookies
        
        # Check if the request was successful
        if response.status_code != 200:
            return None, f"Request failed with status code {response.status_code}"
        
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
                return None, "Captcha value not found in response"
        else:
            return None, "Script tag containing captcha function not found in response"
        
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
        return form_values, None
    
    except Exception as e:
        return None, f"Error getting form values: {e}"

def login_to_website():
    return True, None

def post_to_website(message, form_values):  
    try:  
        date_str = message['date_id'].split('#')[0]
        date_and_time = date_str + ' ' + message['time']
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
        }

        print(f"Payload: { payload }")
        print(f"Headers: { headers }")

        if 'test' in message:
            return True, None
                
        response = requests.post(url, data=payload, headers=headers, cookies=form_values['cookies'])
        
        if response.status_code == 200:
            print("Post successful")
            return True, None
        
        else:
            return False, f"Post failed with status code {response.status_code}: {response.text}"
        
    except Exception as e:
        return False, f"Error posting to website: {e}"

