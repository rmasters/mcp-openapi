from typing import TypedDict
from aiohttp import ClientSession
import openapi_parser.specification as openapi_spec

from http import HTTPMethod


class RegisteredRequest(TypedDict):
    method: HTTPMethod
    path: str
    op: openapi_spec.Operation


class APIClient:
    requests: dict[str, RegisteredRequest]

    def __init__(self, base_url: str):
        self.session = ClientSession(base_url=base_url)
        self.requests = {}

    def add_request(
        self, name: str, method: HTTPMethod, path: str, op: openapi_spec.Operation
    ):
        self.requests[name] = {
            "method": method,
            "path": path,
            "op": op,
        }

    async def call(self, name: str, **kwargs):
        request = self.requests[name]

        path_params = {}
        query_params = {}
        body_params = {}

        for param in request["op"].parameters:
            if param.name not in kwargs:
                continue

            if "{" + param.name + "}" in request["path"]:
                path_params[param.name] = kwargs[param.name]
            else:
                query_params[param.name] = kwargs[param.name]

            if param.name in kwargs:
                path_params[param.name] = kwargs[param.name]

        if request["op"].request_body:
            for content in request["op"].request_body.content:
                if isinstance(content.schema, openapi_spec.Object):
                    for prop in content.schema.properties:
                        body_params[prop.name] = kwargs[prop.name]

        path = request["path"].format(**path_params)

        async with self.session.request(
            request["method"].value, path, params=query_params, json=body_params
        ) as response:
            return await response.text()
