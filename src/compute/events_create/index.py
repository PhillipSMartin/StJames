import os, json, re, uuid
import boto3
from botocore.exceptions import ClientError

TABLE = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
ACCESS_ENUM = {'public', 'private'}
LIST_ENUM = {'moms', 'sojourner', 'patch', 'test'}

DATE_RE    = re.compile(r'^\d{4}-\d{2}-\d{2}$')
DATE_ID_RE = re.compile(r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$')

def bad(status, msg):
    # include CORS for good measure (proxy integration will pass these through)
    return {
        "statusCode": status,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Requested-With",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps({"message": msg})
    }

def ok_created(item, event):
    # Build absolute URL: https://{domain}/{stage}/events/{access}/{date_id}
    rc = event.get("requestContext") or {}
    domain = rc.get("domainName") or ""
    stage  = rc.get("stage") or ""
    # If you use a custom domain with base path mapping, stage may be empty—this still works.
    base = f"https://{domain}"
    path = f"/{stage}" if stage else ""
    location = f"{base}{path}/events/{item['access']}/{item['date_id']}"

    return {
        "statusCode": 201,
        "headers": {
            "Location": location,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Requested-With",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps({"message": "Created", "item": item, "location": location})
    }

def validate_lists(item):
    buckets = {k: set(item.get(k, []) or []) for k in ('post','posting','posted')}
    # allowed values
    for k, vals in buckets.items():
        if not vals.issubset(LIST_ENUM):
            return f"{k} contains invalid values; allowed={sorted(LIST_ENUM)}"
    # exclusivity across lists
    if (buckets['post'] & buckets['posting']) or (buckets['post'] & buckets['posted']) or (buckets['posting'] & buckets['posted']):
        return "A value may not appear in more than one of post/posting/posted."
    return None

def handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
    except Exception:
        return bad(400, "Invalid JSON body")

    access = body.get('access')
    if access not in ACCESS_ENUM:
        return bad(422, "access must be 'public' or 'private'")

    date_id = body.get('date_id')
    date    = body.get('date')

    # Accept either date_id or date
    if isinstance(date_id, str) and DATE_ID_RE.match(date_id):
        pass  # already valid
    elif isinstance(date, str) and DATE_RE.match(date):
        date_id = f"{date}#{uuid.uuid4()}"
    else:
        return bad(422, "Provide either 'date_id' as 'YYYY-MM-DD#GUID' or 'date' as 'YYYY-MM-DD'.")

    # Build item
    item = {
        'access': access,
        'date_id': date_id,
    }
    for f in ('title','time','description','post','posting','posted'):
        if f in body:
            item[f] = body[f]

    # Validate lists
    err = validate_lists(item)
    if err:
        return bad(422, err)

    # Create with no-overwrite condition
    try:
        TABLE.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(access) AND attribute_not_exists(date_id)'
        )
        return ok_created(item, event)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return bad(409, "Item already exists")
        return bad(500, f"DynamoDB error: {e.response['Error']['Message']}")
