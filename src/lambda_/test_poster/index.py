import json

def handler(event, context):
    print("request:", json.dumps(event))

    return {
        'statusCode': 200,
        'body': json.dumps(event["body"]) }
