import os, json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

TABLE = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
ACCESS_ENUM = {'public', 'private'}

def bad(status, msg):
    return {"statusCode": status, "body": json.dumps({"message": msg})}

def jsonify(obj):
    """Recursively convert Decimal -> int/float so json.dumps works."""
    if isinstance(obj, list):
        return [jsonify(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        # keep integers as int, others as float
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def ok(items):
    items = jsonify(items)
    return {"statusCode": 200, "body": json.dumps({"items": items})}

def handler(event, context):
    path_params = (event.get('pathParameters') or {})
    access = path_params.get('access')
    if access not in ACCESS_ENUM:
        return bad(422, "access must be 'public' or 'private'")

    try:
        resp = TABLE.query(
            KeyConditionExpression=Key('access').eq(access),
            ScanIndexForward=False,  # newest first
            Limit=100
        )
        items = resp.get('Items', [])
        # derive client-friendly "date" (won't error if missing)
        for it in items:
            did = it.get('date_id') or ''
            it['date'] = did.split('#')[0] if isinstance(did, str) else ''
        return ok(items)
    except Exception as e:
        return bad(500, f"Query failed: {e}")
