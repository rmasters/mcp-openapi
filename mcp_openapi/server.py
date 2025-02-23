from http import HTTPMethod
from typing import Annotated, Any
from mcp.server.fastmcp.server import FastMCP, Settings as FastMCPSettings
from mcp.server.fastmcp.tools.tool_manager import (
    ToolManager,
    logger as tool_manager_logger,
)
from mcp.server.fastmcp.tools.base import Tool
from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata, ArgModelBase
from pydantic import Field, WithJsonSchema, create_model
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
import yarl

from openapi_parser import parse as openapi_parser_parse
import openapi_parser.specification as openapi_spec

from mcp_openapi.api_client import APIClient
from mcp_openapi.settings import Settings as OpenAPISettings


class ServerFactory:
    openapi_settings: OpenAPISettings
    fastmcp_settings: FastMCPSettings

    def __init__(
        self, openapi_settings: OpenAPISettings, fastmcp_settings: FastMCPSettings
    ):
        self.openapi_settings = openapi_settings
        self.fastmcp_settings = fastmcp_settings

    async def load_openapi_spec(self) -> openapi_spec.Specification:
        """Load the OpenAPI spec from the URL - this should resolve any components in other specs as well"""
        return openapi_parser_parse(
            uri=str(self.openapi_settings.openapi_url), strict_enum=False
        )

    async def build_server(self) -> FastMCP:
        """Build the server from the OpenAPI spec"""

        spec = await self.load_openapi_spec()

        # Get first server URL
        # TODO: Allow this to be overridden by a CLI arg
        if not spec.servers:
            raise ValueError("No servers found in OpenAPI spec")

        server_url = yarl.URL(spec.servers[0].url)
        if not server_url.is_absolute():
            # TODO: test this jank
            server_url = yarl.URL(str(self.openapi_settings.openapi_url)).join(
                server_url
            )

        # Initialize API client
        api_client = APIClient(str(server_url).rstrip("/"))

        # Register each path operation as a tool
        # TODO: Filter by tags
        # TODO: Filter by operation_id matches
        # TODO: Filter by HTTP method
        # TODO: Restrict to specified subset of paths
        mcp = FastMCP()
        for path in spec.paths:
            for op in path.operations:
                tool = tool_from_path(api_client, path, op)
                register_tool(mcp, tool)

        return mcp


def register_tool(server: FastMCP, tool: Tool) -> None:
    tool_manager: ToolManager = server._tool_manager

    # Duplicated code from ToolManager.add_tool, without the Tool.function introspector
    # Perhaps we should go lower level than FastMCP, might make all the pydantic stuff redundant
    existing = tool_manager._tools.get(tool.name)
    if existing:
        if tool_manager.warn_on_duplicate_tools:
            tool_manager_logger.warning(f"Tool already exists: {tool.name}")
            return

    tool_manager._tools[tool.name] = tool


def json_schema_type_to_python_type(
    schema: openapi_spec.Schema,
) -> type[int | str | bool | list[Any] | dict[str, Any] | None | float]:
    """Convert a JSON Schema type to a Python type - likely incomplete"""

    if schema.type == openapi_spec.DataType.INTEGER:
        return int
    if schema.type == openapi_spec.DataType.STRING:
        return str
    if schema.type == openapi_spec.DataType.BOOLEAN:
        return bool
    if schema.type == openapi_spec.DataType.ARRAY:
        return list[Any]
    if schema.type == openapi_spec.DataType.OBJECT:
        return dict[str, Any]
    if schema.type == openapi_spec.DataType.NUMBER:
        return float
    if schema.type == openapi_spec.DataType.NULL:
        return type(None)

    raise ValueError(f"Unsupported type: {schema.type}")


def tool_params_from_operation(op: openapi_spec.Operation) -> FuncMetadata:
    """
    Collect the parameters required for the operation

    This can include path parameters, query parameters, and body parameters.

    TODO: Here be bugs for sure.

    """

    def create_param(
        p: openapi_spec.Parameter | openapi_spec.Property,
        is_required: bool | None = None,
    ) -> tuple[type, FieldInfo]:
        type_ = json_schema_type_to_python_type(p.schema)

        if isinstance(p, openapi_spec.Parameter):
            is_required = is_required if is_required is not None else p.required

        annotation = Annotated[
            type_,  # type: ignore[valid-type]  # This seems impossible to make mypy happy, hopefully we can remove it later
            Field(),
            WithJsonSchema(
                {
                    "title": p.name,
                    "type": p.schema.type.value,
                    "description": p.schema.description,
                    "default": p.schema.default,
                    "required": is_required,
                    "enum": p.schema.enum,
                    "examples": p.schema.example,
                    "deprecated": p.schema.deprecated,
                    "readOnly": p.schema.read_only,
                    "writeOnly": p.schema.write_only,
                }
            ),
        ]

        default = p.schema.default if p.schema.default else PydanticUndefined

        field_info = FieldInfo.from_annotated_attribute(
            annotation,  # type: ignore[arg-type]
            default,
        )
        assert field_info.annotation is not None
        return field_info.annotation, field_info

    params = {}

    if op.parameters:
        for p in op.parameters:
            params[p.name] = create_param(p)

    if rb := op.request_body:
        for content in rb.content:
            if isinstance(content.schema, openapi_spec.Object):
                for prop in content.schema.properties:
                    params[prop.name] = create_param(
                        prop, is_required=prop.name in content.schema.required
                    )

    arg_model = create_model(
        f"{op.operation_id}Arguments",
        **params,
        __base__=ArgModelBase,  # type: ignore[call-overload]
    )

    return FuncMetadata(
        arg_model=arg_model,
    )


def tool_from_path(
    api_client: APIClient, path: openapi_spec.Path, op: openapi_spec.Operation
) -> Tool:
    """Convert a path operation to a tool"""

    async def fn(*args, **kwargs) -> str:
        """The function that will be called when the tool is invoked"""
        assert op.operation_id is not None
        return await api_client.call(op.operation_id, *args, **kwargs)

    # Register the operation with the API client, so it can match up parameters to path/query/body parameters
    assert op.operation_id is not None
    api_client.add_request(
        op.operation_id, HTTPMethod(op.method.value.upper()), path.url, op
    )

    # Create the tool metadata
    fn_metadata = tool_params_from_operation(op)

    # Build the tool
    return Tool(
        fn=fn,
        fn_metadata=fn_metadata,
        name=op.operation_id,
        description=" - ".join(filter(None, [op.summary, op.description])),
        parameters=fn_metadata.arg_model.model_json_schema(),
        is_async=True,
        context_kwarg=None,
    )
