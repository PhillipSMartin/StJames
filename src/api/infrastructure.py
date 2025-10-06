from aws_cdk import (
    aws_apigateway as apigw,
)
from constructs import Construct
import re


class StJamesApi(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        self.events_api = apigw.RestApi(
            self, 'EventsApi',
            rest_api_name='StJames Events Api',
            deploy_options=apigw.StageOptions(
                throttling_rate_limit=50,
                throttling_burst_limit=100
            )
        )


class StJamesApiResources(Construct):
    """
    Extends the existing API with /post-events, /status (existing),
    and now a fully modeled /events REST surface for DynamoDB CRUD.

    Lambda integrations for /events are temporarily mocked as 501 so
    the API shape can ship now; swap to LambdaIntegration later.
    """
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        api: StJamesApi = kwargs['api']
        post_events_handler = kwargs['post_events_handler']
        status_handler = kwargs['status_handler']

        # --------------------
        # Existing endpoints
        # --------------------
        post_events = api.events_api.root.add_resource('post-events')
        post_events_integration = apigw.LambdaIntegration(post_events_handler)
        post_events.add_method('POST', post_events_integration)

        status = api.events_api.root.add_resource('status')
        status_integration = apigw.LambdaIntegration(status_handler)
        status.add_method('POST', status_integration,
            request_parameters={
                'method.request.querystring.old-status': False,  # Optional
                'method.request.querystring.new-status': True,   # Required
                'method.request.querystring.sort-key': True,     # Required
                'method.request.querystring.website': True       # Required
            }
        )

        # --------------------
        # New /events surface
        # --------------------
        # Shared request validators
        body_validator = apigw.RequestValidator(
            api.events_api, 'EventsBodyValidator',
            rest_api=api.events_api,
            validate_request_body=True,
            validate_request_parameters=False
        )
        params_validator = apigw.RequestValidator(
            api.events_api, 'EventsParamsValidator',
            rest_api=api.events_api,
            validate_request_body=False,
            validate_request_parameters=True
        )

        # JSON Schema pieces
        allowed_lists_enum = ['moms', 'sojourner', 'patch', 'test']  # from sample item
        date_guid_regex = r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$'

        # Full event model for POST (create)
        event_create_model = apigw.Model(
            api.events_api, 'EventCreateModel',
            rest_api=api.events_api,
            content_type='application/json',
            model_name='EventCreate',
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title='EventCreate',
                type=apigw.JsonSchemaType.OBJECT,
                additional_properties=False,
                required=['access', 'date_id', 'title'],
                properties={
                    'access': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING,
                        enum=['public', 'private']
                    ),
                    'date_id': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING,
                        pattern=date_guid_regex
                    ),
                    'title': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'time': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'description': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'posted': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING,
                            enum=allowed_lists_enum
                        )
                    ),
                    'posting': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING,
                            enum=allowed_lists_enum
                        )
                    ),
                    'post': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING,
                            enum=allowed_lists_enum
                        )
                    )
                }
            )
        )

        # Update model (same fields but all optional; keys come from path)
        event_update_model = apigw.Model(
            api.events_api, 'EventUpdateModel',
            rest_api=api.events_api,
            content_type='application/json',
            model_name='EventUpdate',
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title='EventUpdate',
                type=apigw.JsonSchemaType.OBJECT,
                additional_properties=False,
                properties={
                    'title': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'time': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'description': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'posted': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING,
                            enum=allowed_lists_enum
                        )
                    ),
                    'posting': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING,
                            enum=allowed_lists_enum
                        )
                    ),
                    'post': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING,
                            enum=allowed_lists_enum
                        )
                    )
                }
            )
        )

        # Basic 4xx/5xx responses for the mocks
        default_method_responses = [
            apigw.MethodResponse(status_code='200'),
            apigw.MethodResponse(status_code='201'),
            apigw.MethodResponse(status_code='204'),
            apigw.MethodResponse(status_code='400'),
            apigw.MethodResponse(status_code='404'),
            apigw.MethodResponse(status_code='422'),
            apigw.MethodResponse(status_code='500'),
        ]

        # Mock integrations (swap to LambdaIntegration later)
        mock_501 = apigw.MockIntegration(
            integration_responses=[
                apigw.IntegrationResponse(
                    status_code='501',
                    response_templates={'application/json': '{"message":"Not Implemented"}'}
                )
            ],
            passthrough_behavior=apigw.PassthroughBehavior.WHEN_NO_MATCH,
            request_templates={'application/json': '{"statusCode": 501}'}
        )

        # /events
        events = api.events_api.root.add_resource('events')
        events.add_cors_preflight(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allow_headers=['Content-Type', 'Authorization', 'X-Requested-With']
        )

        # POST /events  (create)
        events.add_method(
            http_method='POST',
            integration=mock_501,
            request_models={'application/json': event_create_model},
            request_validator=body_validator,
            method_responses=default_method_responses
        )

        # /events/{access}
        events_access = events.add_resource('{access}')
        # Validate "access" via requestParameters & a requestValidator (API GW can't enum path directly,
        # but we can document and re-validate in Lambda; still we keep a param validator here.)
        events_access.add_method(
            http_method='GET',
            integration=mock_501,
            request_parameters={'method.request.path.access': True},
            request_validator=params_validator,
            method_responses=default_method_responses
        )

        # /events/{access}/{date_id}
        events_item = events_access.add_resource('{date_id}')

        # GET item
        events_item.add_method(
            http_method='GET',
            integration=mock_501,
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=params_validator,
            method_responses=default_method_responses
        )

        # PUT item (update)
        events_item.add_method(
            http_method='PUT',
            integration=mock_501,
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=apigw.RequestValidator(
                api.events_api, 'EventsPutValidator',
                rest_api=api.events_api,
                validate_request_body=True,
                validate_request_parameters=True
            ),
            request_models={'application/json': event_update_model},
            method_responses=default_method_responses
        )

        # DELETE item
        events_item.add_method(
            http_method='DELETE',
            integration=mock_501,
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=params_validator,
            method_responses=default_method_responses
        )
