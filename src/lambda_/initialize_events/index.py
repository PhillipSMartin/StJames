import json
import boto3
import os
import uuid

def is_table_empty(table):
    response = table.scan(
        Select='COUNT',
        Limit=1
    )
    return response['Count'] == 0

def handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    s3 = boto3.client('s3')

    table = dynamodb.Table(os.environ['TABLE_NAME'])
    bucket_name = os.environ['BUCKET_NAME']
    file_key = os.environ['FILE_KEY']

    print(f"Checking if table {os.environ['TABLE_NAME']} is empty")
    if is_table_empty(table):
        print(f"Table is empty. Fetching data from S3 bucket {bucket_name}, file {file_key}")
        try:
            response = s3.get_object(Bucket=bucket_name, Key=file_key)
            calendar_data = json.loads(response['Body'].read().decode('utf-8'))
            print(f"Successfully fetched data from S3. Number of items: {len(calendar_data)}")
        except Exception as e:
            print(f"Error fetching data from S3: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps('Error fetching data from S3')
            }

        print("Inserting data into DynamoDB table")
        try:
            with table.batch_writer() as batch:
                for index, item in enumerate(calendar_data):
                    item['date_id'] = f"{item['date']}#{str(uuid.uuid4())}"
                    del item['date']
                    if item.get('access') == 'public':
                        item['post'] = ['gov', 'moms', 'sojourner', 'patch']
                    batch.put_item(Item=item)
                    if (index + 1) % 100 == 0:
                        print(f"Inserted {index + 1} items")
            print(f"Successfully inserted {len(calendar_data)} items into DynamoDB")
        except Exception as e:
            print(f"Error inserting data into DynamoDB: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps('Error inserting data into DynamoDB')
            }

        return {
            'statusCode': 200,
            'body': json.dumps('Data inserted successfully')
        }
    else:
        print("Table is not empty, no data inserted")
        return {
            'statusCode': 200,
            'body': json.dumps('Table is not empty, no data inserted')
        }
