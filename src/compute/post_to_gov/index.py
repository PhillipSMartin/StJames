import boto3
import json
import os
import requests

from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

website = 'gov'
session = requests.Session()
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

def calculate_week_and_julian(date_string):
    # Parse the input date string
    date = datetime.strptime(date_string, "%Y-%m-%d")
    
    # Calculate the week number
    week_number = date.isocalendar()[1]
    
    # Calculate the Julian date
    julian_date = date.timetuple().tm_yday
    
    return week_number, julian_date

def get_times(message):
    start_time_str = message['time']
    if ':' not in start_time_str:
        start_time_str = start_time_str.replace(' ', ':00 ')
    start_time_obj = datetime.strptime(start_time_str, '%I:%M %p')

    if 'endtime' in message:
        end_time_str = message['endtime']
        if ':' not in end_time_str:
            end_time_str = end_time_str.replace(' ', ':00 ')
        end_time_obj = datetime.strptime(end_time_str, '%I:%M %p')
    else:
        end_time_obj = start_time_obj + timedelta(hours=1)

    start_time_12hr = start_time_obj.strftime('%I:%M')
    end_time_12hr = end_time_obj.strftime('%I:%M')
    start_time_24hr = start_time_obj.strftime('%H:%M')
    end_time_24hr = end_time_obj.strftime('%H:%M')

    return start_time_12hr, end_time_12hr, start_time_24hr, end_time_24hr

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
        global session
        secret = get_secret()

        response = session.get(login_url)
        if response.status_code == 200:
            csrf_token = None
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', {'type': 'application/json', 'class': 'joomla-script-options new'})
    
            if script_tag:       
                json_data = json.loads(script_tag.string)
                csrf_token = json_data.get('csrf.token')

            if not csrf_token:
                return False, 'CSRF token not found.'
        
            payload = {
                'Submit': '',
                csrf_token: '1',  # CSRF token
                'option': 'com_users',
                'password': secret['password'],
                'return': 'aW5kZXgucGhwp0I0ZW1pZD0xMTc=',
                'task': 'user.login',
                'username': secret['username']
            }

            additional_headers = {
                'sec-ch-ua': '"Google Chrome";v="89", "Chromium";v="89", ";Not A Brand";v="99"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1'
            }

            # Send the POST request
            session.headers.update(additional_headers)
            response = session.post(login_url, data=payload, headers=additional_headers)
            
            if (response.status_code == 200) and (2 <= len(session.cookies)):
                print(f'Login successful')
                return True, None
            else:
                return False, f"Login failed: status code={response.status_code}, number of cookies={len(session.cookies)}"

    except Exception as e:
        return False, f"Unable to login: {e}"

def post_to_website(message):  
    try:
        global session

        date_str = message['date_id'].split('#')[0]
        _, julian_date = calculate_week_and_julian(date_str)

        current_date = datetime.now()
        current_date_format1 = current_date.strftime("%m/%d/%Y")
        current_month, current_day, current_year = current_date_format1.split('/')   
        current_week_number, _ = calculate_week_and_julian(f"{current_year}-{current_month}-{current_day}")

        year, month, day = date_str.split('-')
        date_format1 = f"{month}/{day}/{year}"
        date_format2 = f"{year}-{int(month)}-{int(day)}"


        start_time_12hr, end_time_12hr, start_time_24hr, end_time_24hr = get_times(message)

        form_data = {
            "Itemid": "117",
            "access": "1",
            "boxchecked": "0",
            "bymonth": f"{int(current_month)}",
            "bymonthday": f"{int(day)}",
            "byweekno": f"{current_week_number}",
            "byyearday": f"{julian_date}",
            "catid[]": ["13"],
            "contact_info": "",
            "count": "1",
            "countuntil": "count",
            "day": f"{int(day)}",
            "end_12h": end_time_12hr,
            "end_ampm": "none",
            "end_time": end_time_24hr,
            "evid": "0",
            "extra_info": "",
            "freq": "none",
            "ics_id": "1",
            "irregular": current_date_format1,
            "jevcontent": f"<p>{message['description']}<p>",
            "jevtype": "icaldb",
            "location": "Church of St. James the Less, 10 Church Lane, Scarsdale, NY",
            "month": f"{int(month)}",
            "multiday": "1",
            "option": "com_jevents",
            "publish_down": current_date_format1,
            "publish_down2": date_format2,
            "publish_up": date_format1,
            "publish_up2": date_format2,  
            "rinterval": "1", 
            "rp_id": "0",  
            "start_12h": start_time_12hr,
            "start_ampm": "none",
            "start_time": start_time_24hr,
            "state": "1",  # 1 for published, 0 for unpublished
            "task": "icalevent.save",
            "title": message["title"],
            "until": current_date_format1,
            "until2": date_format2,
            "updaterepeats": "0",
            "valid_dates": "1", 
            "view12Hour": "1",
            "weekdays[]": ["5"], 
            "weeknums[]": ["1","2","3","4","5"],    
            "year": year
        }

        print(f"Form data: {form_data}")

        if 'test' in message:
            return True, None
        
        response = session.post(post_url, data=form_data)
    
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            alert_divs = soup.find_all('div', class_='alert-message')
            for div in alert_divs:
                alert_text = div.get_text(strip=True) 
                print(alert_text)

            print("Post successful")
            return True, None
        
        else:
            return False, f"Post failed with status code {response.status_code}: {response.text}"
        
    except Exception as e:
        return False, f"Error posting to website: {e}"


