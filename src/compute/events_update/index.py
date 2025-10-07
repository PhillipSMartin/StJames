import os, json, re
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

def jsonify(obj):
    if isinstance(obj, list):
        return [jsonify(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

TABLE = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
ACCESS_ENUM = {'public', 'private'}
LIST_ENUM = {'moms','sojourner','patch','test'}
DATE_ID_RE = re.compile(r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$')

def bad(status, msg):
    return {"statusCode": status, "body": json.dumps({"message": msg})}

def ok(item):
    return {"statusCode": 200, "body": json.dumps({"message": "Updated", "item": jsonify(item)})}

def validate_lists(payload):
    buckets = {k: set(payload.get(k, []) or []) for k in ('post','posting','posted')}
    # Validate allowed
    for k, vals in buckets.items():
        if not vals.issubset(LIST_ENUM):
            return f"{k} contains invalid values; allowed={sorted(LIST_ENUM)}"
    # Cross-list exclusivity
    if (buckets['post'] & buckets['posting']) or (buckets['post'] & buckets['posted']) or (buckets['posting'] & buckets['posted']):
        return "A value may not appear in more than one of post/posting/posted."
    return None

def handler(event, context):
    p = (event.get('pathParameters') or {})
    access = p.get('access')
    date_id = p.get('date_id')

    if access not in ACCESS_ENUM:
        return bad(422, "access must be 'public' or 'private'")
    if not isinstance(date_id, str) or not DATE_ID_RE.match(date_id):
        return bad(422, "date_id must match 'YYYY-MM-DD#GUID'")

    try:
        body = json.loads(event.get('body') or '{}')
    except Exception:
        return bad(400, "Invalid JSON body")

    # Only allow these fields to be updated
    allowed_fields = {'title','time','description','post','posting','posted'}
    unknown = set(body.keys()) - allowed_fields
    if unknown:
        return bad(422, f"Unknown fields: {sorted(unknown)}")

    # Validate list constraints if any lists provided
    if any(k in body for k in ('post','posting','posted')):
        err = validate_lists(body)
        if err:
            return bad(422, err)

    # Read existing to merge (we keep simple for clarity)
    try:
        existing = TABLE.get_item(Key={'access': access, 'date_id': date_id}, ConsistentRead=True).get('Item')
        if not existing:
            return bad(404, "Not found")
    except Exception as e:
        return bad(500, f"Read before update failed: {e}")

    # Merge and write back (idempotent put)
    new_item = dict(existing)
    for k, v in body.items():
        new_item[k] = v

    try:
        TABLE.put_item(
            Item=new_item,
            ConditionExpression='attribute_exists(access) AND attribute_exists(date_id)'
        )
        return ok(new_item)
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ConditionalCheckFailedException':
            return bad(404, "Not found")
        return bad(500, f"DynamoDB error: {e.response['Error']['Message']}")
