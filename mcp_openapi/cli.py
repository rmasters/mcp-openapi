from typing import Annotated, TypedDict
import typer

from mcp_openapi.async_typer import AsyncTyper
from mcp_openapi.server import ServerFactory
from mcp_openapi.settings import Settings as OpenAPISettings
from mcp.server.fastmcp.server import Settings as FastMCPSettings


app = AsyncTyper()


class State(TypedDict):
    server_factory: ServerFactory


state: State | None = None


@app.callback()
def main(
    openapi_url: Annotated[
        str, typer.Option(help="The URL of the OpenAPI spec to serve")
    ],
    fastmcp_debug: Annotated[
        bool, typer.Option(help="Enable debug mode for the MCP server")
    ] = False,
    fastmcp_log_level: Annotated[
        str, typer.Option(help="The log level for the MCP server")
    ] = "INFO",
    fastmcp_sse_host: Annotated[
        str, typer.Option(help="The host to serve the MCP server on")
    ] = "0.0.0.0",
    fastmcp_sse_port: Annotated[
        int, typer.Option(help="The port to serve the MCP server on")
    ] = 8000,
):
    openapi_settings: OpenAPISettings = OpenAPISettings.model_validate(
        {"openapi_url": openapi_url}
    )
    fastmcp_settings: FastMCPSettings = FastMCPSettings.model_validate(
        {
            "debug": fastmcp_debug,
            "log_level": fastmcp_log_level,
            "host": fastmcp_sse_host,
            "port": fastmcp_sse_port,
        }
    )

    global state
    state = {
        "server_factory": ServerFactory(openapi_settings, fastmcp_settings),
    }


@app.command()
async def sse():
    assert state["server_factory"] is not None

    server = await state["server_factory"].build_server()
    await server.run_sse_async()


@app.command()
async def stdio():
    assert state["server_factory"] is not None

    server = await state["server_factory"].build_server()
    await server.run_stdio_async()
