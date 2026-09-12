"""Bounded observations of a fixed gateway, shared by every dashboard viewer."""

import asyncio
import os
import time
from collections import deque
from datetime import UTC, datetime
from typing import Literal

import httpx
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from mcp_stack.config import StackConfig
from services.dashboard.metrics import Sample, Totals, parse_metrics, sample_delta


class Observation(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class ServerStatus(Observation):
    state: Literal["UNKNOWN", "STARTING", "ONLINE", "DEGRADED", "OFFLINE", "CIRCUIT_OPEN"]
    catalogAvailable: bool
    readyToRoute: bool
    stale: bool
    catalogAgeSeconds: float | None = Field(default=None, ge=0)
    tools: int = Field(ge=0)
    circuit: Literal["CLOSED", "OPEN", "HALF_OPEN"]


class GatewayStatus(Observation):
    version: str = Field(max_length=100)
    ready: bool
    generation: int = Field(ge=0)
    tools: int = Field(ge=0)
    servers: dict[str, ServerStatus]


class ToolSummary(Observation):
    name: str
    description: str | None
    input_schema: bool
    output_schema: bool


class ToolContract(Observation):
    name: str
    description: str | None
    inputSchema: dict[str, JsonValue]
    outputSchema: dict[str, JsonValue] | None


class ContractView(Observation):
    tool: ToolContract
    observed_at: str | None
    available: bool


class Catalog(Observation):
    available: bool = False
    observed_at: str | None = None
    tools: list[ToolSummary] = Field(default_factory=list)


class ServerView(Observation):
    id: str
    display_name: str
    namespace: str
    enabled: bool
    status: ServerStatus | None
    metrics: Totals | None
    average_ms: float | None
    error_percent: float | None


class Overview(Observation):
    stack_version: str
    protocol: str
    endpoint: str
    poll_seconds: float
    observed_at: str | None
    metrics_at: str | None
    status_available: bool
    metrics_available: bool
    status_error: str | None
    metrics_error: str | None
    gateway: GatewayStatus | None
    servers: list[ServerView]
    totals: Totals | None
    average_ms: float | None
    p95_upper_ms: float | None
    p95_overflow: bool
    history: list[Sample]
    catalog: Catalog


def bearer(env_name: str | None) -> dict[str, str]:
    if env_name is None:
        return {}
    token = os.environ.get(env_name)
    if not token:
        raise ValueError("configured dashboard credential is missing")
    return {"Authorization": "Bearer " + token}


def error_code(error: Exception) -> str:
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "TIMEOUT"
    if isinstance(error, httpx.HTTPStatusError):
        return "AUTH_FAILED" if error.response.status_code in {401, 403} else "UNAVAILABLE"
    if isinstance(error, httpx.TransportError):
        return "UNREACHABLE"
    return "INVALID_RESPONSE"


class Monitor:
    def __init__(self, config: StackConfig, gateway_url: str = "http://mcp-one:8000"):
        self.config = config
        self.gateway_url = gateway_url.rstrip("/")
        admin_headers = bearer(config.gateway.admin_token_env)
        mcp_headers = bearer(config.gateway.token_env)
        self.http = httpx.AsyncClient(
            headers={**admin_headers, "Accept-Encoding": "identity"},
            timeout=config.dashboard.timeout_seconds,
            limits=httpx.Limits(max_connections=4),
            trust_env=False,
            follow_redirects=False,
        )
        self.mcp_http = httpx2.AsyncClient(
            headers=mcp_headers,
            timeout=config.dashboard.timeout_seconds,
            limits=httpx2.Limits(max_connections=2),
            trust_env=False,
            follow_redirects=False,
        )
        self.status: GatewayStatus | None = None
        self.totals: Totals | None = None
        self.server_metrics: dict[str, Totals] = {}
        self.status_at: str | None = None
        self.metrics_at: str | None = None
        self.status_error: str | None = "STARTING"
        self.metrics_error: str | None = "STARTING"
        self.history: deque[Sample] = deque(maxlen=120)
        self.catalog = Catalog()
        self.contracts: dict[str, ToolContract] = {}
        self._catalog_due = 0.0
        self._previous: Totals | None = None
        self._previous_time = 0.0

    async def close(self) -> None:
        await self.http.aclose()
        await self.mcp_http.aclose()

    async def read(self, path: Literal["/status", "/metrics"]) -> bytes:
        async with asyncio.timeout(self.config.dashboard.timeout_seconds):
            async with self.http.stream("GET", self.gateway_url + path) as response:
                response.raise_for_status()
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise ValueError("compressed observations are not accepted")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 4_194_304:
                        raise ValueError("observation exceeds size limit")
                return bytes(body)

    async def observe_status(self) -> None:
        try:
            status = GatewayStatus.model_validate_json(await self.read("/status"))
            expected = {server.id for server in self.config.enabled_servers}
            if set(status.servers) != expected:
                raise ValueError("gateway and manifest inventory differ")
            self.status = status
            self.status_at = datetime.now(UTC).isoformat()
            self.status_error = None
        except Exception as error:
            # Never expose exception strings: they can include headers or response bodies.
            self.status_error = error_code(error)

    async def observe_metrics(self) -> None:
        at = datetime.now(UTC).isoformat()
        now = time.monotonic()
        try:
            metrics = parse_metrics(
                (await self.read("/metrics")).decode(),
                {server.id for server in self.config.enabled_servers},
            )
            totals = metrics.totals
            self.server_metrics = metrics.servers
            self.history.append(sample_delta(self._previous, totals, now - self._previous_time, at))
            self.totals = self._previous = totals
            self._previous_time = now
            self.metrics_at = at
            self.metrics_error = None
        except Exception as error:
            self.metrics_error = error_code(error)
            self._previous = None
            self.history.append(Sample(at=at, calls_per_minute=None, average_ms=None))

    async def observe_catalog(self) -> None:
        # The fixed, pinned gateway already bounds/validates its catalog. No downstream
        # URL is accepted from a viewer. SDK owns all discovery and MCP wire semantics.
        try:
            async with asyncio.timeout(self.config.dashboard.timeout_seconds):
                async with Client(
                    streamable_http_client(self.gateway_url + "/mcp", http_client=self.mcp_http),
                    cache=None,
                ) as client:
                    summaries: list[ToolSummary] = []
                    contracts: dict[str, ToolContract] = {}
                    cursor = None
                    cursors: set[str] = set()
                    for _ in range(100):
                        page = await client.list_tools(cursor=cursor)
                        for tool in page.tools:
                            contracts[tool.name] = ToolContract(
                                name=tool.name,
                                description=tool.description,
                                inputSchema=tool.input_schema,
                                outputSchema=tool.output_schema,
                            )
                        summaries.extend(
                            ToolSummary(
                                name=tool.name,
                                description=tool.description,
                                input_schema=True,
                                output_schema=tool.output_schema is not None,
                            )
                            for tool in page.tools
                        )
                        if len(summaries) > self.config.gateway.max_tools:
                            raise ValueError("catalog exceeds configured limit")
                        if not page.next_cursor:
                            break
                        if page.next_cursor in cursors:
                            raise ValueError("repeated catalog cursor")
                        cursor = page.next_cursor
                        cursors.add(cursor)
                    else:
                        raise ValueError("too many catalog pages")
            self.contracts = contracts
            self.catalog = Catalog(
                available=True,
                observed_at=datetime.now(UTC).isoformat(),
                tools=sorted(summaries, key=lambda tool: tool.name),
            )
        except Exception:
            self.catalog = self.catalog.model_copy(update={"available": False})

    async def refresh(self) -> None:
        async with asyncio.TaskGroup() as group:
            group.create_task(self.observe_status())
            group.create_task(self.observe_metrics())
            if time.monotonic() >= self._catalog_due:
                group.create_task(self.observe_catalog())
                self._catalog_due = time.monotonic() + 30

    async def run(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(self.config.dashboard.poll_seconds)

    def overview(self) -> Overview:
        from mcp_stack import __version__

        return Overview(
            stack_version=__version__,
            protocol=self.config.protocol,
            endpoint=self.config.gateway.endpoint,
            poll_seconds=self.config.dashboard.poll_seconds,
            observed_at=self.status_at,
            metrics_at=self.metrics_at,
            status_available=self.status_error is None,
            metrics_available=self.metrics_error is None,
            status_error=self.status_error,
            metrics_error=self.metrics_error,
            gateway=self.status,
            totals=self.totals,
            average_ms=self.totals.average_ms if self.totals else None,
            p95_upper_ms=self.totals.percentile_upper_ms() if self.totals else None,
            p95_overflow=self.totals.p95_overflow if self.totals else False,
            history=list(self.history),
            catalog=self.catalog,
            servers=[
                ServerView(
                    id=server.id,
                    display_name=server.display_name,
                    namespace=server.namespace,
                    enabled=server.enabled,
                    status=self.status.servers.get(server.id) if self.status else None,
                    metrics=self.server_metrics.get(server.id),
                    average_ms=self.server_metrics[server.id].average_ms
                    if server.id in self.server_metrics
                    else None,
                    error_percent=self.server_metrics[server.id].error_percent
                    if server.id in self.server_metrics
                    else None,
                )
                for server in sorted(self.config.servers, key=lambda s: (not s.enabled, s.id))
            ],
        )
