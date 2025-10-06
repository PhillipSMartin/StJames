from aws_cdk import (
    aws_apigateway as apigw,
)
from constructs import Construct


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

        # Ensure ALL default gateway error responses include CORS
        for code in ['DEFAULT_4_XX', 'DEFAULT_5_XX']:
            apigw.GatewayResponse(
                self, f'{code}WithCors',
                rest_api=self.events_api,
                type=getattr(apigw.ResponseType, code),
                response_headers={
                    'Access-Control-Allow-Origin': "'*'",
                    'Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Requested-With'",
                    'Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'"
                },
                templates={'application/json': '{"message":$context.error.messageString}'}
            )


class StJamesApiResources(Construct):
    """
    Wires the REST surface and CORS.
    Expects Lambda handlers passed in via kwargs:
      - post_events_handler, status_handler
      - events_create, events_list, events_get, events_update, events_delete
    """
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        api: StJamesApi = kwargs['api']
        post_events_handler = kwargs['post_events_handler']
        status_handler = kwargs['status_handler']

        events_create = kwargs['events_create']
        events_list   = kwargs['events_list']
        events_get    = kwargs['events_get']
        events_update = kwargs['events_update']
        events_delete = kwargs['events_delete']

        # --------------------
        # Existing endpoints
        # --------------------
        post_events = api.events_api.root.add_resource('post-events')
        post_events.add_method('POST', apigw.LambdaIntegration(post_events_handler))

        status = api.events_api.root.add_resource('status')
        status.add_method(
            'POST',
            apigw.LambdaIntegration(status_handler),
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
        # Request validators (body vs params)
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

        # Shared JSON schema parts
        allowed_lists_enum = ['moms', 'sojourner', 'patch', 'test']
        date_guid_regex = r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$'

        # Create model (accepts either 'date' or 'date_id'; Lambda enforces "at least one")
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
                # Only require access and title; Lambda checks for date/date_id
                required=['access', 'title'],
                properties={
                    'access': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING,
                        enum=['public', 'private']
                    ),
                    'date': apigw.JsonSchema(  # NEW: plain date
                        type=apigw.JsonSchemaType.STRING,
                        pattern=r'^\d{4}-\d{2}-\d{2}$'
                    ),
                    'date_id': apigw.JsonSchema(  # OPTIONAL: full date_id
                        type=apigw.JsonSchemaType.STRING,
                        pattern=r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$'
                    ),
                    'title': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'time': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'description': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'posted': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING, enum=['moms','sojourner','patch','test']
                        )
                    ),
                    'posting': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING, enum=['moms','sojourner','patch','test']
                        )
                    ),
                    'post': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING, enum=['moms','sojourner','patch','test']
                        )
                    )
                }
            )
        )

        # Update model (keys in path, all body fields optional)
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
                            type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum
                        )
                    ),
                    'posting': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum
                        )
                    ),
                    'post': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY,
                        unique_items=True,
                        items=apigw.JsonSchema(
                            type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum
                        )
                    )
                }
            )
        )

        # --------------------
        # Helpers for CORS
        # --------------------
        def method_cors_responses(success_codes: list[str]):
            # Add CORS headers on method responses (declared)
            return [apigw.MethodResponse(
                        status_code=code,
                        response_parameters={
                            'method.response.header.Access-Control-Allow-Origin': True,
                            'method.response.header.Access-Control-Allow-Headers': True,
                            'method.response.header.Access-Control-Allow-Methods': True
                        }
                    ) for code in success_codes] + [
                    apigw.MethodResponse(
                        status_code=code,
                        response_parameters={
                            'method.response.header.Access-Control-Allow-Origin': True,
                            'method.response.header.Access-Control-Allow-Headers': True,
                            'method.response.header.Access-Control-Allow-Methods': True
                        }
                    ) for code in ['400','401','403','404','409','422','500']
                ]

        def integration_cors_response(status_code: str, template: str = None):
            return apigw.IntegrationResponse(
                status_code=status_code,
                response_parameters={
                    'method.response.header.Access-Control-Allow-Origin': "'*'",
                    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Requested-With'",
                    'method.response.header.Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'",
                },
                response_templates={'application/json': template} if template else None
            )

        # --------------------
        # Resources & Methods
        # --------------------
        events = api.events_api.root.add_resource('events')
        events.add_cors_preflight(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allow_headers=['Content-Type', 'Authorization', 'X-Requested-With']
        )

        # POST /events  -> create
        # events.add_method(
        #     http_method='POST',
        #     integration=apigw.LambdaIntegration(events_create),
        #     request_models={'application/json': event_create_model},
        #     request_validator=body_validator,
        #     method_responses=method_cors_responses(['201'])
        # )

        events.add_method(
            http_method='POST',
            integration=apigw.LambdaIntegration(events_create),
            request_models={'application/json': event_create_model},
            request_validator=body_validator,
            method_responses=[
                apigw.MethodResponse(
                    status_code='201',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                        'method.response.header.Location': True,   # <- allow Location header
                    }
                ),
                # keep standard error shapes declared so CORS headers appear there too
                apigw.MethodResponse(
                    status_code='400',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                    }
                ),
                apigw.MethodResponse(
                    status_code='401',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                    }
                ),
                apigw.MethodResponse(
                    status_code='403',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                    }
                ),
                apigw.MethodResponse(
                    status_code='409',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                    }
                ),
                apigw.MethodResponse(
                    status_code='422',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                    }
                ),
                apigw.MethodResponse(
                    status_code='500',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                    }
                ),
            ]
        )

        # /events/{access}
        events_access = events.add_resource('{access}')

        # GET /events/{access} -> list
        events_access.add_method(
            http_method='GET',
            integration=apigw.LambdaIntegration(events_list,
                integration_responses=[
                    integration_cors_response('200'),
                    integration_cors_response('400'),
                    integration_cors_response('401'),
                    integration_cors_response('403'),
                    integration_cors_response('404'),
                    integration_cors_response('500'),
                ]),
            request_parameters={'method.request.path.access': True},
            request_validator=params_validator,
            method_responses=method_cors_responses(['200'])
        )

        # /events/{access}/{date_id}
        events_item = events_access.add_resource('{date_id}')

        # GET item
        events_item.add_method(
            http_method='GET',
            integration=apigw.LambdaIntegration(events_get,
                integration_responses=[
                    integration_cors_response('200'),
                    integration_cors_response('404'),
                    integration_cors_response('422'),
                    integration_cors_response('500'),
                ]),
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=params_validator,
            method_responses=method_cors_responses(['200'])
        )

        # PUT item
        events_item.add_method(
            http_method='PUT',
            integration=apigw.LambdaIntegration(events_update,
                integration_responses=[
                    integration_cors_response('200'),
                    integration_cors_response('404'),
                    integration_cors_response('422'),
                    integration_cors_response('500'),
                ]),
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_models={'application/json': event_update_model},
            request_validator=apigw.RequestValidator(
                api.events_api, 'EventsPutValidator',
                rest_api=api.events_api,
                validate_request_body=True,
                validate_request_parameters=True
            ),
            method_responses=method_cors_responses(['200'])
        )

        # DELETE item
        events_item.add_method(
            http_method='DELETE',
            integration=apigw.LambdaIntegration(events_delete,
                integration_responses=[
                    integration_cors_response('204'),
                    integration_cors_response('404'),
                    integration_cors_response('422'),
                    integration_cors_response('500'),
                ]),
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=params_validator,
            method_responses=method_cors_responses(['204'])
        )
