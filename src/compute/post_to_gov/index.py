import boto3
import json
import os
import requests

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

website = 'gov'
cookies = requests.cookies.RequestsCookieJar()
# cookies.set('c572abe779ec5a9cc255f401d046399e', 'initial_value')
# cookies.set('joomla_user_state', 'logged_out')

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
    date = datetime.strptime(date_string, "%Y-%m-%d")
    
    # Calculate the week number
    week_number = date.isocalendar()[1]
    
    # Calculate the Julian date
    julian_date = date.timetuple().tm_yday
    
    return week_number, julian_date

def get_times(time_string):
    if ':' not in time_string:
        time_string = time_string.replace(' ', ':00 ')
    start_time_obj = datetime.strptime(time_string, '%I:%M %p')
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
    global cookies

    secret = get_secret()

    response = requests.get(login_url)
    if response.status_code == 200:
        cookies.update(response.cookies)
        print(f'Cookies: {cookies}')

        csrf_token = None
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', {'type': 'application/json', 'class': 'joomla-script-options new'})
 
        if script_tag:       
            json_data = json.loads(script_tag.string)
            csrf_token = json_data.get('csrf.token')

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

        # Send the POST request
        print(f"Payload: {payload}")
        response = requests.post(login_url, data=payload, cookies=cookies)
        if response.status_code == 200:
            print(f'Login successful')
            cookies.update(response.cookies)
            print(cookies)
            return False # temporary while testing
    
    print(f'Login failed: status code {response.status_code}')
    print(response.text)
    return False


def post_to_website(message):   

    date_str = message['date_id'].split('#')[0]
    _, julian_date = calculate_week_and_julian(date_str)

    current_date = datetime.now()
    current_date_format1 = current_date.strftime("%m/%d/%Y")
    current_month, current_day, current_year = current_date_format1.split('/')   
    current_week_number, _ = calculate_week_and_julian(f"{current_year}-{current_month}-{current_day}")

    year, month, day = date_str.split('-')
    date_format1 = f"{month}/{day}/{year}"
    date_format2 = f"{year}-{int(month)}-{int(day)}"


    start_time_12hr, end_time_12hr, start_time_24hr, end_time_24hr = get_times(message['time'])

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

    response = requests.post(post_url, data=form_data, cookies=cookies)
  
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        alert_divs = soup.find_all('div', class_='alert-message')
        for div in alert_divs:
            alert_text = div.get_text(strip=True) 
            print(alert_text)
            if alert_text == "Please login first":
                print("Post failed")
                return False
        print("Post successful")
        return True
    
    else:
        print(f"Post failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False
        


