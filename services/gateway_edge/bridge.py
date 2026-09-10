"""Legacy REST endpoints consumed by MCP One; downstream wire is official MCP."""

import asyncio
import os
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException
from jsonschema.exceptions import SchemaError, ValidationError
from mcp import MCPError
from mcp.types import Tool
from opentelemetry import propagate, trace
from pydantic import Field

from mcp_stack.config import ConfigModel, ServerManifest, StackConfig, load_config, local_name
from mcp_stack.http import RequestPolicy, bearer_headers, downstream_client
from mcp_stack.telemetry import configure, trace_fields
from mcp_stack.wire import DEFINITION_KEY, validate_result, validate_tool

log = structlog.get_logger()


def failure_status(error: Exception) -> int:
    """AnyIO task groups can wrap SDK validation failures in ExceptionGroup."""
    if isinstance(error, ExceptionGroup):
        codes = {failure_status(child) for child in error.exceptions}
        return 502 if codes == {502} else 504 if 504 in codes else 503
    if isinstance(error, TimeoutError):
        return 504
    if isinstance(error, (ValueError, RuntimeError, MCPError, SchemaError, ValidationError)):
        return 502
    return 503


class Invocation(ConfigModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    trace_context: dict[str, str] = Field(default_factory=dict)
    request_id: str = Field(max_length=128)


class BridgeCall(ConfigModel):
    tool: str = Field(max_length=128)
    invocation: Invocation


async def catalog(server: ServerManifest, config: StackConfig) -> dict[str, Tool]:
    tools: dict[str, Tool] = {}
    async with asyncio.timeout(server.transport.timeout_seconds):
        async with downstream_client(server, config.gateway.max_payload_bytes) as client:
            cursor = None
            seen_cursors: set[str] = set()
            while True:
                page = await client.list_tools(cursor=cursor)
                for tool in page.tools:
                    validate_tool(
                        tool, config.gateway.max_schema_bytes, config.gateway.max_schema_depth
                    )
                    name = local_name(server.namespace, tool.name)
                    if name in tools:
                        raise ValueError("duplicate tool after namespace normalization")
                    tools[name] = tool
                    if len(tools) > config.gateway.max_tools:
                        raise ValueError("catalog exceeds configured tool limit")
                cursor = page.next_cursor
                if cursor is None:
                    break
                if cursor in seen_cursors:
                    raise ValueError("repeated catalog cursor")
                seen_cursors.add(cursor)
    return tools


async def check_server(server: ServerManifest, config: StackConfig) -> bool:
    try:
        async with asyncio.timeout(
            server.health.timeout_seconds + server.transport.timeout_seconds
        ):
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
                response = await http.get(
                    server.health.url,
                    timeout=server.health.timeout_seconds,
                    headers=bearer_headers(server.transport.token_env),
                )
                response.raise_for_status()
            await catalog(server, config)
        return True
    except Exception:
        return False


def create_app(config: StackConfig | None = None) -> RequestPolicy:
    configure("legacy-bridge")
    config = config or load_config(Path(os.getenv("STACK_CONFIG", "config/stack.yaml")))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    servers = {s.id: s for s in config.enabled_servers}

    def resolve(server_id: str) -> ServerManifest:
        if server_id not in servers:
            raise HTTPException(404, "unknown_server")
        return servers[server_id]

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/servers/{server_id}/health")
    async def health(server_id: str) -> dict[str, str]:
        if not await check_server(resolve(server_id), config):
            raise HTTPException(503, "downstream_unhealthy")
        return {"status": "healthy"}

    @app.get("/servers/{server_id}/tools")
    async def tools(server_id: str) -> dict[str, Any]:
        server = resolve(server_id)
        try:
            listing = await catalog(server, config)
        except Exception as exc:
            log.warning("catalog_rejected", server=server_id, error_type=type(exc).__name__)
            raise HTTPException(502, "invalid_or_unavailable_catalog") from None
        return {
            "tools": [
                {
                    "name": name,
                    "description": tool.description or "",
                    "parameters": {
                        DEFINITION_KEY: tool.model_dump(
                            mode="json", by_alias=True, exclude_none=True
                        )
                    },
                }
                for name, tool in listing.items()
            ]
        }

    @app.post("/servers/{server_id}/call")
    async def call(server_id: str, request: BridgeCall) -> dict[str, Any]:
        server = resolve(server_id)
        started = perf_counter()
        context = propagate.extract(request.invocation.trace_context)
        with trace.get_tracer(__name__).start_as_current_span(
            "legacy.bridge.call", context=context
        ):
            try:
                async with asyncio.timeout(server.transport.timeout_seconds):
                    listing = await catalog(server, config)
                    if request.tool not in listing:
                        raise HTTPException(404, "tool_not_found")
                    tool = listing[request.tool]
                    async with downstream_client(
                        server, config.gateway.max_payload_bytes
                    ) as client:
                        result = await client.call_tool(tool.name, request.invocation.arguments)
                    validate_result(tool, result, config.gateway.max_payload_bytes)
                log.info(
                    "downstream_call",
                    server=server_id,
                    tool=tool.name,
                    requestId=request.invocation.request_id,
                    durationMs=(perf_counter() - started) * 1000,
                    isError=result.is_error,
                    attempts=1,
                    cached=False,
                    **trace_fields(),
                )
                return {"result": result.model_dump(mode="json", by_alias=True, exclude_none=True)}
            except TimeoutError:
                raise HTTPException(504, "downstream_timeout") from None
            except HTTPException:
                raise
            except (ValueError, RuntimeError, MCPError, SchemaError, ValidationError) as exc:
                log.warning(
                    "invalid_downstream_response",
                    server=server_id,
                    error_type=type(exc).__name__,
                    **trace_fields(),
                )
                raise HTTPException(502, "invalid_downstream_response") from None
            except Exception as exc:
                log.warning(
                    "downstream_unavailable",
                    server=server_id,
                    error_type=type(exc).__name__,
                    **trace_fields(),
                )
                raise HTTPException(failure_status(exc), "downstream_failure") from None

    return RequestPolicy(app, config.gateway.max_payload_bytes)
