from typing import Any
from aiohttp import ClientSession
import openapi_parser.specification as openapi_spec

from http import HTTPMethod

import yarl


class APIClient:
    """
    Handles the making of API requests based on an OpenAPI spec.

    TODO: Introduce authentication here.

    """

    spec: openapi_spec.Specification
    base_url: yarl.URL
    session: ClientSession

    def __init__(self, spec: openapi_spec.Specification, spec_url: str):
        self.spec = spec

        self.base_url = extract_base_url(spec, spec_url)
        self.session = ClientSession(base_url=str(self.base_url))

    async def call(
        self,
        method: HTTPMethod,
        path: str,
        query_params: dict[str, Any],
        body: dict[str, Any],
    ):
        async with self.session.request(
            method, path, params=query_params, json=body
        ) as response:
            # TODO: Provide some information about the response for non-2xx
            return await response.text()


def extract_base_url(spec: openapi_spec.Specification, spec_url: str) -> yarl.URL:
    # Get first server URL
    # TODO: Allow this to be overridden by a CLI arg
    if not spec.servers:
        raise ValueError("No servers found in OpenAPI spec")

    server_url = yarl.URL(spec.servers[0].url)
    if not server_url.is_absolute():
        # TODO: test this jank
        # Base URL, if the spec server URL is relative
        base_url = yarl.URL(spec_url)
        server_url = base_url.join(server_url)

    return server_url
