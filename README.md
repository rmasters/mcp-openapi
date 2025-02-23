# MCP-OpenAPI

A [Model Context Protocol][mcp] server that exposes HTTP methods from an OpenAPI spec as tools.

> [!WARNING]
> This is a proof of concept, yet to be fully tested and documented.

## Usage

Each MCP-OpenAPI server exposes operations from a single OpenAPI spec. You could run multiple instances to expose multiple specs.

This package is available on PyPI @ [`mcp-openapi`][pypi]. You can start a server with `uvx mcp-openapi --openapi-url https://httpbin.org/spec.json (sse | stdio)`.

An example Claude config (while running `fastapi dev tests/todos.py` with port 8000):

```json
{
  "mcpServers": {
    "todos": {
    "command": "uvx",
    "args": [
        "mcp-openapi",
        "--openapi-url=http://localhost:8000/openapi.json",
        "stdio"
      ]
    }
  }
}
```

The OpenAPI url can also be passed as an environment variable, `MCP_OPENAPI_URL`.

When running as SSE, you can configure the server with:

- `--fastmcp-sse-host` - the host to serve the MCP server on
- `--fastmcp-sse-port` - the port to serve the MCP server on

There are additional global options:

- `--fastmcp-debug` - enable debug mode for the MCP server
- `--fastmcp-log-level` - the log level for the MCP server

These can also be configured via environment variables using the `FASTMCP_` prefix, e.g. `FASTMCP_LOG_LEVEL=DEBUG`.

### How it works

1. The MCP-OpenAPI server is initialised with an OpenAPI spec URL.
2. The server fetches and parses the OpenAPI spec, and registers each path-operation as a tool.
3. A FastMCP server is started with the registered tools.
4. When a client requests a tool, the MCP server makes a HTTP request to the API and returns the response.

### Supported OpenAPI/Swagger versions

| Swagger 2.0 | OpenAPI 3.0 | OpenAPI 3.1 |
|-------------|-------------|-------------|
| :x: | :heavy_check_mark: | :heavy_check_mark: |

This package supports OpenAPI 3.0 and 3.1 specs, in JSON and YAML formats.

We're using [openapi-parser][openapi-parser] under the hood, which seems to be pretty comprehensive, and supports resolving references to external specs.

### Future configuration options

> [!INFO]
> These are still to be implemented.

#### Restricting endpoints

By default, all endpoints are exposed as tools. You can restrict which endpoints are exposed:

- By path patterns,
- By HTTP method,
- Explicitly listing the individual operations to expose,
- Selecting routes using OpenAPI tags.

### Handling API authentication

MCP-OpenAPI makes API requests to the target API - it can use a global auth token:

- `--auth-token` - a bearer token, or basic credentials in base64 format, used depending on the OpenAPI spec.

It would be nice to be able to make requests using varying authentication tokens (e.g. per client user), but without having the LLM see the tokens. TBD.

[mcp]: https://modelcontextprotocol.io/
[fastapi-openapi]: https://fastapi.tiangolo.com/reference/openapi/models/
[openapi-parser]: https://github.com/manchenkoff/openapi3-parser