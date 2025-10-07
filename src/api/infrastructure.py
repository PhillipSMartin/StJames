from aws_cdk import aws_apigateway as apigw
from constructs import Construct


# ---------- helper: add default 4XX/5XX with CORS (uses your CDK enum spelling) ----------
def add_default_gateway_cors(api: apigw.RestApi, scope: Construct) -> None:
    four_xx = apigw.ResponseType.DEFAULT_4_XX
    five_xx = apigw.ResponseType.DEFAULT_5_XX
    for rtype, rid in [(four_xx, "Default4xxWithCors"), (five_xx, "Default5xxWithCors")]:
        apigw.GatewayResponse(
            scope, rid,
            rest_api=api,
            type=rtype,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Requested-With'",
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
            templates={"application/json": '{"message":$context.error.messageString}'}
        )


class StJamesApi(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        # Rest API (key comes from header)
        self.events_api = apigw.RestApi(
            self, 'EventsApi',
            rest_api_name='StJames Events Api',
            api_key_source_type=apigw.ApiKeySourceType.HEADER,
            deploy_options=apigw.StageOptions(
                throttling_rate_limit=50,
                throttling_burst_limit=100
            )
        )

        # >>> CALL THE HELPER HERE <<<
        add_default_gateway_cors(self.events_api, self)

        # Simple API key + usage plan for Lovable
        self.lovable_key = self.events_api.add_api_key(
            "LovableApiKey",
            api_key_name="lovable-client-key"  # set value=... if you want a fixed token
        )
        self.usage_plan = self.events_api.add_usage_plan(
            "LovableUsagePlan",
            name="LovableUsage",
            throttle=apigw.ThrottleSettings(rate_limit=20, burst_limit=40),
            quota=apigw.QuotaSettings(limit=5000, period=apigw.Period.DAY),
        )
        self.usage_plan.add_api_stage(stage=self.events_api.deployment_stage)
        self.usage_plan.add_api_key(self.lovable_key)


class StJamesApiResources(Construct):
    """
    Wires endpoints & CORS.
    Expects in kwargs:
      - api
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

        # ---------------- existing endpoints ----------------
        post_events = api.events_api.root.add_resource('post-events')
        post_events.add_method('POST', apigw.LambdaIntegration(post_events_handler))

        status = api.events_api.root.add_resource('status')
        status.add_method(
            'POST',
            apigw.LambdaIntegration(status_handler),
            request_parameters={
                'method.request.querystring.old-status': False,
                'method.request.querystring.new-status': True,
                'method.request.querystring.sort-key': True,
                'method.request.querystring.website': True
            }
        )

        # ---------------- /events CRUD surface ----------------
        # Validators
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

        allowed_lists_enum = ['moms', 'sojourner', 'patch', 'test']

        # Create model: accept either 'date' or 'date_id' (Lambda enforces at-least-one)
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
                required=['access', 'title'],
                properties={
                    'access': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING,
                        enum=['public', 'private']
                    ),
                    'date': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING,
                        pattern=r'^\d{4}-\d{2}-\d{2}$'
                    ),
                    'date_id': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING,
                        pattern=r'^\d{4}-\d{2}-\d{2}#[0-9a-fA-F-]{36}$'
                    ),
                    'title': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'time': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'description': apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    'posted': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY, unique_items=True,
                        items=apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum)
                    ),
                    'posting': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY, unique_items=True,
                        items=apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum)
                    ),
                    'post': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY, unique_items=True,
                        items=apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum)
                    )
                }
            )
        )

        # Update model
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
                        type=apigw.JsonSchemaType.ARRAY, unique_items=True,
                        items=apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum)
                    ),
                    'posting': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY, unique_items=True,
                        items=apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum)
                    ),
                    'post': apigw.JsonSchema(
                        type=apigw.JsonSchemaType.ARRAY, unique_items=True,
                        items=apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=allowed_lists_enum)
                    )
                }
            )
        )

        # Helpers to declare + set CORS on method responses
        def method_cors_responses(success_codes):
            common = {
                'method.response.header.Access-Control-Allow-Origin': True,
                'method.response.header.Access-Control-Allow-Headers': True,
                'method.response.header.Access-Control-Allow-Methods': True
            }
            m = [apigw.MethodResponse(status_code=code, response_parameters=common)
                 for code in success_codes]
            for code in ['400', '401', '403', '404', '409', '422', '500']:
                m.append(apigw.MethodResponse(status_code=code, response_parameters=common))
            return m

        events = api.events_api.root.add_resource('events')
        events.add_cors_preflight(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allow_headers=['Content-Type', 'Authorization', 'X-Requested-With']
        )

        # POST /events (returns Location header from Lambda; require API key)
        events.add_method(
            http_method='POST',
            integration=apigw.LambdaIntegration(events_create),
            request_models={'application/json': event_create_model},
            request_validator=body_validator,
            api_key_required=True,
            method_responses=[
                apigw.MethodResponse(
                    status_code='201',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                        'method.response.header.Location': True,
                    }
                ),
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

        # GET /events/{access} (list)
        events_access.add_method(
            http_method='GET',
            integration=apigw.LambdaIntegration(events_list),
            request_parameters={'method.request.path.access': True},
            request_validator=params_validator,
            api_key_required=True,
            method_responses=method_cors_responses(['200'])
        )

        # /events/{access}/{date_id}
        events_item = events_access.add_resource('{date_id}')

        # GET item
        events_item.add_method(
            http_method='GET',
            integration=apigw.LambdaIntegration(events_get),
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=params_validator,
            api_key_required=True,
            method_responses=method_cors_responses(['200'])
        )

        # PUT item
        events_item.add_method(
            http_method='PUT',
            integration=apigw.LambdaIntegration(events_update),
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
            api_key_required=True,
            method_responses=method_cors_responses(['200'])
        )

        # DELETE item
        events_item.add_method(
            http_method='DELETE',
            integration=apigw.LambdaIntegration(events_delete),
            request_parameters={
                'method.request.path.access': True,
                'method.request.path.date_id': True
            },
            request_validator=params_validator,
            api_key_required=True,
            method_responses=method_cors_responses(['204'])
        )
