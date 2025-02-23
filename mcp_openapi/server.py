from mcp.server.lowlevel import Server
from mcp.types import CallToolRequest, ListToolsRequest

from openapi_parser import parse as openapi_parser_parse
import openapi_parser.specification as openapi_spec

from mcp_openapi.settings import Settings as OpenAPISettings
from mcp_openapi.spec_handlers import OpenAPISpecHandler


class ServerFactory:
    openapi_settings: OpenAPISettings

    def __init__(self, openapi_settings: OpenAPISettings):
        self.openapi_settings = openapi_settings

    async def load_openapi_spec(self) -> openapi_spec.Specification:
        """Load the OpenAPI spec from the URL - this should resolve any components in other specs as well"""
        return openapi_parser_parse(
            uri=str(self.openapi_settings.openapi_url), strict_enum=False
        )

    def extract_operations(
        self, spec: openapi_spec.Specification
    ) -> list[openapi_spec.Operation]:
        """Extract the operations from the OpenAPI spec"""
        return [op for path in spec.paths for op in path.operations]

    async def build_server(self) -> Server:
        """Build the server from the OpenAPI spec"""

        spec = await self.load_openapi_spec()
        spec_handler = OpenAPISpecHandler(spec, str(self.openapi_settings.openapi_url))

        server: Server = Server(
            name=spec.info.title,
            version=spec.info.version,
            instructions=f"Use these tools to make API requests to the {spec.info.title} API.\nAPI description:\n{spec.info.description}",
        )

        server.request_handlers[CallToolRequest] = spec_handler.call_tool
        server.request_handlers[ListToolsRequest] = spec_handler.list_tools

        return server
