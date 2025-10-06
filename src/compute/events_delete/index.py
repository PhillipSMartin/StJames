import os, json, re
import boto3
from botocore.exceptions import ClientError

TABLE = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
ACCESS_ENUM = {'public', 'private'}
DATE_ID_RE = re.compile(r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$')

def bad(status, msg):
    return {"statusCode": status, "body": json.dumps({"message": msg})}

def ok():
    return {"statusCode": 204, "body": ""}

def handler(event, context):
    p = (event.get('pathParameters') or {})
    access = p.get('access')
    date_id = p.get('date_id')

    if access not in ACCESS_ENUM:
        return bad(422, "access must be 'public' or 'private'")
    if not isinstance(date_id, str) or not DATE_ID_RE.match(date_id):
        return bad(422, "date_id must match 'YYYY-MM-DD#GUID'")

    try:
        TABLE.delete_item(
            Key={'access': access, 'date_id': date_id},
            ConditionExpression='attribute_exists(access) AND attribute_exists(date_id)'
        )
        return ok()
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ConditionalCheckFailedException':
            return bad(404, "Not found")
        return bad(500, f"DynamoDB error: {e.response['Error']['Message']}")
