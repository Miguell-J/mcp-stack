"""Native MCP facade over the original MCP One REST control plane."""

import asyncio
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
import structlog
from jsonschema import Draft202012Validator, ValidationError
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.caching import CacheHint
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    Tool,
)
from opentelemetry import propagate
from scientific_mcp_contracts import ErrorCategory, ErrorCode
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_stack.config import StackConfig, load_config, qualified_name
from mcp_stack.http import RequestPolicy, read_json
from mcp_stack.telemetry import configure, trace_fields
from mcp_stack.wire import (
    DEFINITION_KEY,
    ERROR_META,
    GATEWAY_META,
    bounded_json,
    error_result,
    legacy_error,
    validate_result,
    validate_tool,
)

log = structlog.get_logger()


class Gateway:
    def __init__(self, config: StackConfig) -> None:
        self.config = config
        self.namespaces = {s.namespace: s.id for s in config.enabled_servers}

    async def one(self, method: str, path: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(
            timeout=self.config.gateway.request_timeout_seconds,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            return await read_json(
                client,
                method,
                self.config.gateway.one_url + path,
                max_bytes=self.config.gateway.max_payload_bytes,
                **kwargs,
            )

    async def catalog(self, *, refresh: bool) -> dict[str, Tool]:
        online: set[str] | None = None
        if refresh:
            await self.one("POST", "/servers/refresh")
            statuses = await self.one("GET", "/servers")
            online = {s["config"]["name"] for s in statuses["servers"] if s["status"] == "online"}
        data = await self.one("GET", "/tools")
        tools: dict[str, Tool] = {}
        for entry in data["tools"]:
            namespace = entry["server_name"]
            if online is not None and namespace not in online:
                continue
            if namespace not in self.namespaces:
                raise ValueError("unconfigured namespace in MCP One catalog")
            tool = Tool.model_validate(entry["parameters"][DEFINITION_KEY])
            name = qualified_name(namespace, tool.name)
            if name != entry["full_name"] or name in tools:
                raise ValueError("duplicate or inconsistent MCP One tool name")
            validate_tool(
                tool, self.config.gateway.max_schema_bytes, self.config.gateway.max_schema_depth
            )
            tools[name] = tool.model_copy(update={"name": name})
        if len(tools) > self.config.gateway.max_tools:
            raise ValueError("aggregate catalog exceeds configured tool limit")
        return tools

    async def list_tools(
        self,
        ctx: ServerRequestContext[Any, Any],
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        if params and params.cursor:
            raise MCPError(-32602, "Unknown catalog cursor")
        try:
            tools = await self.catalog(refresh=True)
        except Exception:
            raise MCPError(-32603, "Gateway catalog unavailable") from None
        return ListToolsResult(tools=list(tools.values()))

    async def call_tool(
        self,
        ctx: ServerRequestContext[Any, Any],
        params: CallToolRequestParams,
    ) -> CallToolResult:
        started = perf_counter()
        request_id = str(uuid4())
        namespace = params.name.partition(".")[0]
        server = self.namespaces.get(namespace, "unknown")
        attempts: int | None = None
        try:
            bounded_json(params.arguments or {}, self.config.gateway.max_payload_bytes)
            tools = await self.catalog(refresh=False)
            if params.name not in tools:
                raise MCPError(-32602, "Unknown tool")
            tool = tools[params.name]
            try:
                Draft202012Validator(tool.input_schema).validate(params.arguments or {})
            except ValidationError:
                result = error_result(
                    ErrorCode.INVALID_ARGUMENT,
                    ErrorCategory.DOMAIN,
                    "Arguments do not match inputSchema.",
                )
                attempts = 0
            else:
                carrier: dict[str, str] = {}
                propagate.inject(carrier)
                # MCP One forwards this opaque invocation object without needing trace awareness.
                response = await self.one(
                    "POST",
                    "/call",
                    json={
                        "tool": params.name,
                        "arguments": {
                            "arguments": params.arguments or {},
                            "trace_context": carrier,
                            "request_id": request_id,
                        },
                    },
                )
                if response["success"]:
                    result = CallToolResult.model_validate(response["result"])
                    validate_result(tool, result, self.config.gateway.max_payload_bytes)
                    attempts = 1
                else:
                    result = legacy_error(response.get("error"))
                    attempts = (
                        0
                        if response.get("error")
                        in {
                            "server_offline",
                            "circuit_open",
                            "server_not_found",
                            "tool_not_found",
                        }
                        else 1
                    )
        except MCPError:
            raise
        except (httpx.TimeoutException, TimeoutError):
            result = error_result(
                ErrorCode.TIMEOUT,
                ErrorCategory.INFRASTRUCTURE,
                "Gateway request timed out.",
                retryable=True,
            )
        except httpx.HTTPError:
            result = error_result(
                ErrorCode.DOWNSTREAM_UNAVAILABLE,
                ErrorCategory.INFRASTRUCTURE,
                "MCP One is unavailable.",
                retryable=True,
            )
        except Exception as exc:
            log.warning("gateway_response_rejected", error_type=type(exc).__name__)
            result = error_result(
                ErrorCode.INTERNAL_ERROR,
                ErrorCategory.INFRASTRUCTURE,
                "Gateway rejected an invalid downstream response.",
            )
        metadata: dict[str, Any] = {
            "requestId": request_id,
            "server": server,
            "tool": params.name,
            "durationMs": round((perf_counter() - started) * 1000, 3),
            "cached": False,
            **trace_fields(),
        }
        if attempts is not None:
            metadata["attempts"] = attempts
        result.meta = {**(result.meta or {}), GATEWAY_META: metadata}
        error = (result.meta or {}).get(ERROR_META, {})
        log.info(
            "gateway_call",
            **metadata,
            isError=result.is_error,
            errorCode=error.get("code"),
            errorCategory=error.get("category"),
        )
        return result

    async def health(self, request: Request) -> JSONResponse:
        statuses: dict[str, str] = {"native MCP edge": "healthy"}
        try:
            await self.one("GET", "/health")
            statuses["mcp-one"] = "healthy"
        except Exception:
            statuses["mcp-one"] = "unhealthy"

        async def downstream(server_id: str) -> tuple[str, str]:
            try:
                async with httpx.AsyncClient(trust_env=False) as client:
                    response = await client.get(
                        f"{self.config.gateway.bridge_url}/servers/{server_id}/health",
                        timeout=self.config.gateway.request_timeout_seconds,
                    )
                    response.raise_for_status()
                return server_id, "healthy"
            except Exception:
                return server_id, "unhealthy"

        statuses.update(
            await asyncio.gather(*(downstream(s.id) for s in self.config.enabled_servers))
        )
        healthy = all(s == "healthy" for s in statuses.values())
        return JSONResponse(
            {"status": "healthy" if healthy else "unhealthy", "services": statuses},
            status_code=200 if healthy else 503,
        )


def create_app(config: StackConfig | None = None) -> RequestPolicy:
    configure("gateway-edge")
    config = config or load_config(Path(os.getenv("STACK_CONFIG", "config/stack.yaml")))
    gateway = Gateway(config)
    server: Server[Any] = Server(
        "scientific-stack",
        version="0.1.0",
        instructions="Scientific results carry data, context, diagnostics and provenance. "
        "Check isError and diagnostics before interpreting a result. Demo tools are test fixtures.",
        on_list_tools=gateway.list_tools,
        on_call_tool=gateway.call_tool,
        cache_hints={"tools/list": CacheHint(ttl_ms=config.gateway.catalog_ttl_seconds * 1000)},
    )

    async def live(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=config.gateway.max_payload_bytes,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "gateway-edge:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
        ),
        custom_starlette_routes=[
            Route("/health", gateway.health),
            Route("/ready", gateway.health),
            Route("/live", live),
        ],
    )
    return RequestPolicy(app, config.gateway.max_payload_bytes, token_env="MCP_STACK_TOKEN")
