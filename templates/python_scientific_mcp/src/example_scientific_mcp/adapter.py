"""Translate library values to typed scientific MCP results."""

import logging
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from scientific_mcp_contracts import ContractModel, Provenance, ScientificResult
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .domain_port import DomainLibrary, ExampleLibrary


class DescriptionData(ContractModel):
    description: str


def create_server(library: DomainLibrary | None = None) -> MCPServer:
    library = library or ExampleLibrary()
    mcp = MCPServer("example-scientific-mcp", version="0.1.0")

    @mcp.tool(
        name="example.describe",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def describe() -> Annotated[CallToolResult, ScientificResult[DescriptionData]]:
        value = library.describe()
        result = ScientificResult[DescriptionData](
            data=DescriptionData(description=value.description),
            provenance=Provenance(
                library=value.name, library_version=value.version, deterministic=True
            ),
        )
        return CallToolResult(
            content=[TextContent(type="text", text=f"Description of {value.name}.")],
            structured_content=result.model_dump(mode="json", exclude_none=True),
        )

    return mcp


def create_app() -> Starlette:
    logging.basicConfig(level=logging.WARNING)
    trace.set_tracer_provider(
        TracerProvider(resource=Resource.create({"service.name": "example-scientific-mcp"}))
    )

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    app = create_server().streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=1048576,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["localhost:*", "127.0.0.1:*", "example-scientific-mcp:*"],
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    )
    app.routes.append(Route("/health", health))
    return app
