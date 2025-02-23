from http import HTTPMethod
import logging
from mcp import Tool
from mcp.types import TextContent
from mcp.types import ServerResult, CallToolRequest, CallToolResult, ListToolsResult
import openapi_parser.specification as openapi_spec

from mcp_openapi.api_client import APIClient


class OpenAPISpecHandler:
    """
    Handles the mapping of OpenAPI operations to MCP tools.

    Provides two request handlers for an mcp.Server:

    - list_tools: Returns a list of tools based on the OpenAPI spec.
    - call_tool: Makes an API request using the operation and returns the result.

    """

    spec: openapi_spec.Specification
    spec_url: str

    operations: dict[str, tuple[openapi_spec.Path, openapi_spec.Operation]]

    def __init__(self, spec: openapi_spec.Specification, spec_url: str):
        self.spec = spec
        self.spec_url = spec_url

        self.operations = {}
        for path in self.spec.paths:
            for op in path.operations:
                if op.operation_id is None:
                    raise ValueError(f"Operation {op} has no operation_id")

                self.operations[op.operation_id] = (path, op)

        self.api_client = APIClient(self.spec, self.spec_url)

        self.logger = logging.getLogger(__name__)

    async def list_tools(self) -> ServerResult:
        tools: list[Tool] = []

        # Register each path operation as a tool
        # TODO: Filter by tags
        # TODO: Filter by operation_id matches
        # TODO: Filter by HTTP method
        # TODO: Restrict to specified subset of paths
        for op_id, (path, op) in self.operations.items():
            self.logger.debug(
                f"Registering operation {op_id} as a tool ({op.method=} {path.url=})"
            )

            input_schema = {}
            required_fields = []

            # TODO: From 5 mins of searching, it seems like not every LLM supports nested
            # objects in the input schema, so we will consolidate them until we figure out
            # how widespread that is (OpenAPI certainly might not support it, as of mid-2024).

            # Add path parameters to the input schema
            for param in op.parameters:
                if param.name in input_schema:
                    raise ValueError(f"Duplicate parameter name: {param.name}")

                self.logger.debug(
                    f"Adding parameter {param.name} to tool {op_id} ({param.schema=} {param.required=})"
                )

                input_schema[param.name] = param.schema
                if param.required:
                    required_fields.append(param.name)

            # Add request body parameters to the input schema
            if op.request_body:
                for content in op.request_body.content:
                    schema = content.schema
                    # TODO: Handle non-object bodies, e.g. images
                    if isinstance(schema, openapi_spec.Object):
                        for prop in schema.properties:
                            if prop.name in input_schema:
                                raise ValueError(
                                    f"Duplicate parameter name: {prop.name}"
                                )

                            input_schema[prop.name] = prop.schema
                            if prop.name in schema.required:
                                required_fields.append(prop.name)

            description = " - ".join(filter(None, [op.summary, op.description]))
            self.logger.debug(
                f"Adding tool {op_id}, {description=} {input_schema=} {required_fields=}"
            )
            tools.append(
                Tool(
                    name=op_id,
                    description=description,
                    inputSchema={
                        "type": "object",
                        "properties": input_schema,
                        "required": required_fields,
                    },
                )
            )

        return ServerResult(ListToolsResult(tools=tools))

    async def call_tool(self, request: CallToolRequest) -> ServerResult:
        path, op = self.operations[request.params.name]

        # TODO: The mixed-bag parameter names as described above also apply here.

        # Build the path using parameters
        url_path = path.url
        for param in op.parameters:
            if param.location == "path":
                url_path = url_path.replace(
                    "{" + param.name + "}", str(request.params.arguments[param.name])
                )

        # Map out the parameters from the request
        query_params = self._extract_query_params(op, request)
        body_params = self._extract_body_params(op, request)
        all_params = list(query_params.keys()) + list(body_params.keys())

        required_params = self._get_required_params(op, request)
        if required_params - set(all_params):
            raise ValueError(
                f"Missing required parameters: {required_params - set(all_params)}"
            )

        # Call the API
        result = await self.api_client.call(
            HTTPMethod(op.method.value.upper()), url_path, query_params, body_params
        )

        return ServerResult(
            CallToolResult(content=[TextContent(type="text", text=result)])
        )

    def _extract_query_params(
        self, op: openapi_spec.Operation, request: CallToolRequest
    ) -> dict[str, str]:
        if not request.params.arguments:
            return {}

        query_params: dict[str, str] = {}
        for param in op.parameters:
            if param.location == "query":
                query_params[param.name] = str(request.params.arguments[param.name])
        return query_params

    def _extract_body_params(
        self, op: openapi_spec.Operation, request: CallToolRequest
    ) -> dict[str, str]:
        if not request.params.arguments or not op.request_body:
            return {}

        body_params: dict[str, str] = {}
        for content in op.request_body.content:
            schema = content.schema
            # TODO: Handle non-object bodies, e.g. images
            if isinstance(schema, openapi_spec.Object):
                for prop in schema.properties:
                    if prop.name not in request.params.arguments:
                        raise ValueError(
                            f"Missing required body parameter: {prop.name}"
                        )

                    body_params[prop.name] = str(request.params.arguments[prop.name])

        return body_params

    def _get_required_params(
        self, op: openapi_spec.Operation, request: CallToolRequest
    ) -> set[str]:
        required_params: set[str] = set()
        for param in op.parameters:
            if param.required:
                required_params.add(param.name)

        if op.request_body:
            for content in op.request_body.content:
                schema = content.schema
                if isinstance(schema, openapi_spec.Object):
                    for prop in schema.properties:
                        if prop.name in schema.required:
                            required_params.add(prop.name)

        return required_params
