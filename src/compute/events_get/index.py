import os, json, re
import boto3
from decimal import Decimal
from urllib.parse import unquote

TABLE = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
ACCESS_ENUM = {'public', 'private'}
DATE_ID_RE = re.compile(r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$')

def normalize_path_ids(p):
    access = (p or {}).get('access')
    date_id_raw = (p or {}).get('date_id', '')
    date_id = unquote(date_id_raw)  # turns %23 back into '#'
    return access, date_id

def jsonify(obj):
    if isinstance(obj, list):
        return [jsonify(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def bad(status, msg):
    return {"statusCode": status, "body": json.dumps({"message": msg})}

def ok(item):
    return {"statusCode": 200, "body": json.dumps(jsonify(item))}

def handler(event, context):
    access, date_id = normalize_path_ids(event.get('pathParameters'))

    if access not in ACCESS_ENUM:
        return bad(422, "access must be 'public' or 'private'")
    if not isinstance(date_id, str) or not DATE_ID_RE.match(date_id):
        return bad(422, "date_id must match 'YYYY-MM-DD#GUID'")

    try:
        resp = TABLE.get_item(Key={'access': access, 'date_id': date_id}, ConsistentRead=True)
        item = resp.get('Item')
        if not item:
            return bad(404, "Not found")
        return ok(item)
    except Exception as e:
        return bad(500, f"Get failed: {e}")
