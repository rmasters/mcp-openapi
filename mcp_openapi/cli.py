import logging
from typing import Annotated, TypedDict
import typer
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
import uvicorn
from mcp_openapi.async_typer import AsyncTyper
from mcp_openapi.server import ServerFactory
from mcp_openapi.settings import LogLevel, Settings as OpenAPISettings


app = AsyncTyper()


class State(TypedDict):
    settings: OpenAPISettings
    server_factory: ServerFactory


state: State | None = None


@app.callback()
def main(
    openapi_url: Annotated[str, typer.Option(help="URL of the OpenAPI spec to serve")],
    log_level: Annotated[
        LogLevel, typer.Option(help="Python log level")
    ] = LogLevel.INFO,
):
    settings: OpenAPISettings = OpenAPISettings.model_validate(
        {"openapi_url": openapi_url, "log_level": log_level.value}
    )

    logging.basicConfig(level=log_level.value)

    global state
    state = {
        "settings": settings,
        "server_factory": ServerFactory(settings),
    }


@app.command()
async def sse(
    sse_host: Annotated[
        str, typer.Option(help="The host to serve the MCP server on")
    ] = "0.0.0.0",
    sse_port: Annotated[
        int, typer.Option(help="The port to serve the MCP server on")
    ] = 8000,
    debug: Annotated[
        bool, typer.Option(help="Enable Starlette server debug mode")
    ] = False,
):
    assert state is not None

    mcp_server = await state["server_factory"].build_server()

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    starlette_app = Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    config = uvicorn.Config(
        starlette_app,
        host=sse_host,
        port=sse_port,
        log_level=state["settings"].log_level.value,
    )
    server = uvicorn.Server(config)
    await server.serve()


@app.command()
async def stdio():
    assert state is not None

    server = await state["server_factory"].build_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
