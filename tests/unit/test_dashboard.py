import asyncio
import json
from dataclasses import dataclass

import httpx
import pytest
from pydantic import ValidationError

from mcp_stack.config import StackConfig, load_config
from mcp_stack.render import compose_config
from services.dashboard.app import create_app
from services.dashboard.metrics import Totals, parse_metrics, sample_delta
from services.dashboard.monitor import Monitor

SERVER = "mock-scientific-mcp"
STATUS = {
    "version": "1.0.0rc1",
    "ready": True,
    "generation": 1,
    "tools": 5,
    "servers": {
        SERVER: {
            "state": "ONLINE",
            "catalogAvailable": True,
            "readyToRoute": True,
            "stale": False,
            "catalogAgeSeconds": 2,
            "tools": 5,
            "circuit": "CLOSED",
            "error": "NEVER_EXPOSE_THIS",
            "capabilities": {"secret": "NEVER_EXPOSE_THIS"},
        }
    },
}
METRICS = """
# TYPE mcp_one_tool_calls_total counter
mcp_one_tool_calls_total{server="mock-scientific-mcp",outcome="success"} 8
mcp_one_tool_calls_total{server="mock-scientific-mcp",outcome="domain_error"} 2
mcp_one_tool_calls_total{server="arbitrary-label",outcome="success"} 1000
mcp_one_tool_calls_total{server="",outcome="unknown_tool"} 1
mcp_one_tool_latency_seconds_sum{server="mock-scientific-mcp"} 0.5
mcp_one_tool_latency_seconds_count{server="mock-scientific-mcp"} 10
mcp_one_catalog_cache_total{server="",outcome="hit"} 5
mcp_one_catalog_cache_total{server="",outcome="miss"} 2
mcp_one_catalog_tools{server="mock-scientific-mcp"} 5
"""


@dataclass
class GatewayStub:
    status: int = 200
    calls: int = 0
    body: bytes | None = None

    async def handle(self, request):
        self.calls += 1
        assert request.method == "GET"
        assert request.url.host == "mcp-one"
        assert request.url.path in {"/status", "/metrics"}
        if self.status != 200:
            return httpx.Response(self.status, text="NEVER_EXPOSE_THIS")
        if self.body is not None:
            return httpx.Response(200, content=self.body)
        if request.url.path == "/status":
            return httpx.Response(200, json=STATUS)
        return httpx.Response(200, text=METRICS)


@pytest.fixture
async def observation():
    monitor = Monitor(load_config())
    await monitor.http.aclose()
    stub = GatewayStub()
    monitor.http = httpx.AsyncClient(transport=httpx.MockTransport(stub.handle))
    # Catalog is covered by the real SDK integration test, not an HTTP imitation.
    monitor._catalog_due = float("inf")
    try:
        yield monitor, stub
    finally:
        await monitor.close()


def test_monitoring_metrics_and_counter_reset():
    totals = parse_metrics(METRICS, {SERVER}).totals
    assert totals.calls == 11
    assert totals.domain_errors == 2
    assert totals.average_ms == 50
    assert totals.cache_hits == 5 and totals.cache_misses == 2
    sample = sample_delta(Totals(calls=6, latency_count=5, latency_seconds=0.2), totals, 5, "now")
    assert sample.calls_per_minute == 60
    assert sample.average_ms == 60
    reset = sample_delta(totals, Totals(), 5, "now")
    assert reset.calls_per_minute is None and reset.average_ms is None
    assert sample_delta(None, totals, 5, "now").calls_per_minute is None


@pytest.mark.parametrize(
    "body",
    [
        "invalid text",
        'mcp_one_catalog_tools{server="mock-scientific-mcp"} NaN',
        'mcp_one_catalog_tools{server="mock-scientific-mcp"} -1',
    ],
)
def test_bad_metrics_do_not_fabricate_zero(body):
    with pytest.raises(ValueError):
        parse_metrics(body, {SERVER})


async def test_failure_retains_snapshot_and_recovers_without_fabricated_samples(observation):
    monitor, stub = observation
    await monitor.refresh()
    first = monitor.overview()
    assert first.status_available and first.metrics_available
    assert first.gateway.ready and first.totals.calls == 11
    assert "NEVER_EXPOSE_THIS" not in first.model_dump_json()
    stub.status = 503
    await monitor.refresh()
    failed = monitor.overview()
    assert not failed.status_available and not failed.metrics_available
    assert failed.gateway == first.gateway and failed.observed_at == first.observed_at
    assert failed.history[-1].calls_per_minute is None
    assert failed.status_error == "UNAVAILABLE"
    stub.status = 200
    await monitor.refresh()
    assert monitor.overview().status_available
    assert monitor.history[-1].calls_per_minute is None
    await monitor.refresh()
    assert monitor.history[-1].calls_per_minute == 0


@pytest.mark.parametrize("body", [b"x" * 4_194_305, b"not-json", b'{"ready":true}'])
async def test_invalid_and_oversized_status_retains_valid_snapshot(observation, body):
    monitor, stub = observation
    await monitor.refresh()
    stub.body = body
    await monitor.observe_status()
    assert monitor.status_error == "INVALID_RESPONSE"
    assert monitor.status.ready


async def test_inventory_drift_fails_explicitly(observation):
    monitor, stub = observation
    stub.body = json.dumps({**STATUS, "servers": {}}).encode()
    await monitor.observe_status()
    assert monitor.status_error == "INVALID_RESPONSE"


async def test_timeout_and_auth_are_distinguishable(observation):
    monitor, stub = observation
    stub.status = 401
    await monitor.refresh()
    assert monitor.status_error == "AUTH_FAILED"

    async def stalled(request):
        await asyncio.sleep(60)

    monitor.config.dashboard.timeout_seconds = 0.1
    await monitor.http.aclose()
    monitor.http = httpx.AsyncClient(transport=httpx.MockTransport(stalled))
    await monitor.observe_status()
    assert monitor.status_error == "TIMEOUT"


async def test_read_only_local_api_assets_and_lifecycle(observation):
    monitor, stub = observation
    app = create_app(monitor.config, monitor)
    async with app.router.lifespan_context(app):
        await monitor.refresh()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://127.0.0.1:8766"
        ) as client:
            assert (await client.get("/health")).json() == {"alive": True}
            response = await client.get("/api/overview")
            assert response.status_code == 200
            assert "NEVER_EXPOSE_THIS" not in response.text
            assert response.headers["cache-control"] == "no-store"
            assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
            calls = stub.calls
            for _ in range(10):
                assert (await client.get("/api/overview")).status_code == 200
            assert stub.calls == calls  # browser refresh cannot hammer the gateway
            for path in [
                "/api/overview",
                "/api/contracts/demo.echo",
                "/refresh",
                "/call",
                "/config",
            ]:
                assert (await client.post(path, json={})).status_code in {404, 405}
            assert (await client.get("/api/overview?url=http://evil.example")).status_code == 200
            assert stub.calls == calls
            for path in [
                "/",
                "/assets/app.js",
                "/assets/theme.js",
                "/assets/style.css",
                "/assets/mark.svg",
            ]:
                assert (await client.get(path)).status_code == 200
            assert (await client.get("/api/contracts/no-such-tool")).status_code == 404
            assert (await client.get("/assets/config.yaml")).status_code == 404
            assert (
                await client.get("/api/overview", headers={"Host": "attacker.example"})
            ).status_code == 403
            assert (
                await client.get("/api/overview", headers={"Origin": "https://attacker.example"})
            ).status_code == 403
            assert (
                await client.get("/api/overview", headers={"Sec-Fetch-Site": "cross-site"})
            ).status_code == 403
            assert (
                await client.get("/api/overview", headers={"Origin": "http://127.0.0.1:8766"})
            ).status_code == 200
    assert monitor.http.is_closed and monitor.mcp_http.is_closed
    assert not any(task.get_name() == "dashboard-observer" for task in asyncio.all_tasks())


def test_dashboard_compose_loopback_optional_and_secret_references(monkeypatch):
    data = load_config().model_dump()
    data["gateway"].update(token_env="UPSTREAM_TEST_TOKEN", admin_token_env="ADMIN_TEST_TOKEN")
    next(s for s in data["servers"] if s["enabled"])["transport"]["token_env"] = (
        "DOWNSTREAM_TEST_TOKEN"
    )
    config = StackConfig.model_validate(data)
    service = compose_config(config)["services"]["dashboard"]
    assert service["ports"] == ["127.0.0.1:8766:8080"]
    assert service["read_only"] and service["user"] == "10001:10001"
    assert service["volumes"] == ["./config:/app/config:ro"]
    assert "ADMIN_TEST_TOKEN" in service["environment"]
    assert "UPSTREAM_TEST_TOKEN" in service["environment"]
    assert "DOWNSTREAM_TEST_TOKEN" not in service["environment"]
    monkeypatch.delenv("UPSTREAM_TEST_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_TEST_TOKEN", raising=False)
    with pytest.raises(ValueError, match="credential is missing"):
        Monitor(config)
    config.dashboard.enabled = False
    assert "dashboard" not in compose_config(config)["services"]
    config.dashboard.enabled = True
    config.dashboard.bind = "::1"
    assert config.dashboard.url == "http://[::1]:8766"
    assert compose_config(config)["services"]["dashboard"]["ports"] == ["[::1]:8766:8080"]
    config.servers = []
    assert "build" in compose_config(config)["services"]["dashboard"]


@pytest.mark.parametrize("change", [{"bind": "0.0.0.0"}, {"port": 8765}, {"poll_seconds": 0.1}])
def test_invalid_dashboard_configuration(change):
    data = load_config().model_dump()
    data["dashboard"].update(change)
    with pytest.raises(ValidationError):
        StackConfig.model_validate(data)
