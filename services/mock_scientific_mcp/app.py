"""Small real MCP server. Algorithms here are fixtures only."""

import asyncio
import hashlib
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.caching import CacheHint
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ResourceLink, ToolAnnotations
from pydantic import AnyUrl, Field
from scientific_mcp_contracts import (
    ArtifactReference,
    CheckStatus,
    Completeness,
    ContractModel,
    DiagnosticCheck,
    Diagnostics,
    DiagnosticWarning,
    ErrorCategory,
    ErrorCode,
    Matrix,
    Provenance,
    ScientificContext,
    ScientificResult,
    Severity,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_stack.telemetry import configure, trace_fields
from mcp_stack.wire import error_result, result_for


class EchoData(ContractModel):
    message: str


class MatrixData(ContractModel):
    matrix: Matrix


class ArtifactData(ContractModel):
    artifact: ArtifactReference


READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
FIXTURE_BYTES = b'{"fixture":true}\n'


def provenance() -> Provenance:
    return Provenance(
        library="mock-fixture",
        library_version="0.1.0",
        backend="python",
        algorithm="fixture",
        precision="exact",
        deterministic=True,
    )


def create_server() -> MCPServer:
    server = MCPServer(
        "mock-scientific-mcp", version="0.1.0", cache_hints={"tools/list": CacheHint(ttl_ms=0)}
    )

    @server.tool(name="demo.echo", annotations=READ_ONLY)
    def echo(
        message: Annotated[str, Field(max_length=4096)],
    ) -> Annotated[CallToolResult, ScientificResult[EchoData]]:
        result = result_for(
            ScientificResult[EchoData](data=EchoData(message=message), provenance=provenance()),
            "Echo fixture completed.",
        )
        result.meta = {**(result.meta or {}), "io.github.miguell-j.mock/trace": trace_fields()}
        return result

    @server.tool(name="demo.identity_matrix", annotations=READ_ONLY)
    def identity_matrix(
        size: Annotated[int, Field(ge=1, le=8)] = 2,
    ) -> Annotated[CallToolResult, ScientificResult[MatrixData]]:
        matrix = Matrix(
            shape=(size, size),
            components=[[float(i == j) for j in range(size)] for i in range(size)],
        )
        return result_for(
            ScientificResult[MatrixData](
                data=MatrixData(matrix=matrix),
                context=ScientificContext(domain="fixture", conventions={"indices": "zero-based"}),
                diagnostics=Diagnostics(
                    warnings=[
                        DiagnosticWarning(
                            code="FIXTURE_ONLY",
                            severity=Severity.INFO,
                            message="Integration fixture, not a scientific backend.",
                        )
                    ],
                    checks=[
                        DiagnosticCheck(
                            name="dimensions",
                            status=CheckStatus.PASSED,
                            value=[size, size],
                            expected=[size, size],
                        )
                    ],
                    completeness=Completeness.COMPLETE,
                ),
                provenance=provenance(),
            ),
            f"Identity fixture of size {size}.",
        )

    @server.tool(name="demo.contract_error", annotations=READ_ONLY)
    def contract_error() -> Annotated[CallToolResult, ScientificResult[EchoData]]:
        return error_result(
            ErrorCode.INVALID_DOMAIN, ErrorCategory.DOMAIN, "Intentional domain error fixture."
        )

    @server.tool(name="demo.slow", annotations=READ_ONLY)
    async def slow(
        seconds: Annotated[float, Field(ge=0, le=10)] = 0.1,
    ) -> Annotated[CallToolResult, ScientificResult[EchoData]]:
        await asyncio.sleep(seconds)
        return result_for(
            ScientificResult[EchoData](data=EchoData(message="finished"), provenance=provenance()),
            "Delay fixture completed.",
        )

    @server.resource("fixture://demo/sample")
    def sample() -> str:
        return FIXTURE_BYTES.decode()

    @server.tool(name="demo.artifact", annotations=READ_ONLY)
    def artifact() -> Annotated[CallToolResult, ScientificResult[ArtifactData]]:
        reference = ArtifactReference(
            uri=AnyUrl("fixture://demo/sample"),
            name="sample.json",
            media_type="application/json",
            size_bytes=len(FIXTURE_BYTES),
            sha256=hashlib.sha256(FIXTURE_BYTES).hexdigest(),
            description="Small fixture resource served by the mock MCP.",
        )
        result = result_for(
            ScientificResult[ArtifactData](
                data=ArtifactData(artifact=reference), provenance=provenance()
            ),
            "Fixture artifact reference.",
        )
        result.content.append(
            ResourceLink(
                type="resource_link",
                uri=str(reference.uri),
                name=reference.name,
                mime_type=reference.media_type,
            )
        )
        return result

    return server


def create_app() -> Starlette:
    configure("mock-scientific-mcp")

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "mock-scientific-mcp"})

    app = create_server().streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=1048576,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "mock-scientific-mcp:*"],
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    )
    app.routes.append(Route("/health", health))
    return app
