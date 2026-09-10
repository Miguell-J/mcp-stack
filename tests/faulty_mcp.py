"""Fault injection server, only launched by tests. Uses the actual SDK transport."""

import os
from pathlib import Path

from mcp.server import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from scientific_mcp_contracts import ScientificResult, schema_for
from starlette.responses import JSONResponse
from starlette.routing import Route

from services.mock_scientific_mcp.app import EchoData


def create_app():
    state = Path(os.environ["STACK_FAULT_FILE"])
    tool = Tool(
        name="demo.echo",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema=schema_for(ScientificResult[EchoData]),
    )

    async def listing(ctx, params):
        mode = state.read_text()
        if mode == "duplicate":
            return ListToolsResult(tools=[tool, tool.model_copy(update={"name": "echo"})])
        if mode == "schema":
            return ListToolsResult(
                tools=[
                    tool.model_copy(
                        update={
                            "input_schema": {
                                "type": "object",
                                "properties": {"x": {"type": "not_a_type"}},
                            }
                        }
                    )
                ]
            )
        if mode == "external_ref":
            return ListToolsResult(
                tools=[
                    tool.model_copy(
                        update={
                            "input_schema": {"type": "object", "$ref": "http://127.0.0.1:1/secrets"}
                        }
                    )
                ]
            )
        return ListToolsResult(tools=[tool])

    async def call(ctx, params):
        return CallToolResult(
            content=[TextContent(type="text", text="Invalid fixture")],
            structured_content={"data": {"message": 42}},
        )

    async def health(request):
        return JSONResponse({"status": "healthy"})

    return Server("fault-injection", on_list_tools=listing, on_call_tool=call).streamable_http_app(
        stateless_http=True, json_response=True, custom_starlette_routes=[Route("/health", health)]
    )
