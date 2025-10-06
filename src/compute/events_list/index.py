import os, json, re
import boto3

TABLE = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
ACCESS_ENUM = {'public', 'private'}

def bad(status, msg):
    return {"statusCode": status, "body": json.dumps({"message": msg})}

def ok(items):
    return {"statusCode": 200, "body": json.dumps({"items": items})}

def handler(event, context):
    path_params = (event.get('pathParameters') or {})
    access = path_params.get('access')
    if access not in ACCESS_ENUM:
        return bad(422, "access must be 'public' or 'private'")

    # Simple list: latest first (assumes date_id begins with sortable YYYY-MM-DD)
    try:
        resp = TABLE.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('access').eq(access),
            ScanIndexForward=False,  # descending
            Limit=100
        )
        return ok(resp.get('Items', []))
    except Exception as e:
        return bad(500, f"Query failed: {e}")
