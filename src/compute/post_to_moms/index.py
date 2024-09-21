import json

def handler(event, context):
    parsed_event = json.loads(event["Records"][0]["Sns"]["Message"])
    print("request:", json.dumps(parsed_event))

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Successfully processed SNS event'})
    }
