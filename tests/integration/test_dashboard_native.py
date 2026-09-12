import httpx
import httpx2
import pytest
import yaml
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mcp_stack.render import one_config
from services.dashboard.app import create_app
from services.dashboard.monitor import Monitor
from tests.conftest import LiveStack

pytestmark = pytest.mark.integration


async def test_dashboard_observes_real_native_gateway(live_stack):
    monitor = Monitor(live_stack.config, live_stack.admin_url)
    try:
        await monitor.refresh()
        state = monitor.overview()
        assert state.status_available and state.gateway.ready
        assert state.metrics_available and state.totals.catalog_bytes > 0
        assert state.catalog.available
        names = {tool.name for tool in state.catalog.tools}
        assert {"demo.identity_matrix", "demo.contract_error", "demo.artifact"} <= names
        assert all(tool.input_schema and tool.output_schema for tool in state.catalog.tools)
        async with httpx.AsyncClient() as client:
            direct = (await client.get(live_stack.admin_url + "/status")).json()
        assert state.gateway.tools == direct["tools"] == len(names)
        assert state.servers[0].status.circuit == "CLOSED"
        # Compare the modal API with definitions obtained directly from the native
        # scientific fixture. Nested $defs, required fields and metadata are intact.
        async with httpx2.AsyncClient(trust_env=False) as http:
            async with Client(
                streamable_http_client(
                    live_stack.config.enabled_servers[0].transport.url, http_client=http
                ),
                cache=None,
            ) as client:
                originals = (await client.list_tools()).tools
        app = create_app(monitor.config, monitor)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://127.0.0.1:8766"
        ) as dashboard:
            for tool in originals:
                name = tool.name if tool.name.startswith("demo.") else "demo." + tool.name
                response = await dashboard.get("/api/contracts/" + name)
                assert response.status_code == 200
                assert response.json()["available"]
                contract = response.json()["tool"]
                assert contract["outputSchema"] == tool.output_schema
                assert contract["inputSchema"] == tool.input_schema
            monitor.status_error = "UNREACHABLE"
            stale = (await dashboard.get("/api/contracts/demo.identity_matrix")).json()
            assert not stale["available"]
            assert stale["tool"]["outputSchema"]
            assert "outputSchema" not in (await dashboard.get("/api/overview")).text
    finally:
        await monitor.close()


async def test_authenticated_observation_and_real_gateway_outage(tmp_path, monkeypatch):
    stack = LiveStack(tmp_path)
    stack.config.gateway.token_env = "DASHBOARD_TEST_UPSTREAM"
    stack.config.gateway.admin_token_env = "DASHBOARD_TEST_ADMIN"
    stack.one_config_path.write_text(yaml.safe_dump(one_config(stack.config)))
    # Separate test-only credentials prove the admin and MCP channels aren't mixed.
    for key, value in {
        "DASHBOARD_TEST_UPSTREAM": "test-only-upstream",
        "DASHBOARD_TEST_ADMIN": "test-only-admin",
    }.items():
        monkeypatch.setenv(key, value)
        stack.env[key] = value
    monitor = Monitor(stack.config, stack.admin_url)
    try:
        stack.start("mock")
        stack.start("one")
        await monitor.refresh()
        assert monitor.overview().status_available
        assert monitor.overview().metrics_available
        assert monitor.catalog.available and len(monitor.catalog.tools) == 5
        assert "test-only" not in monitor.overview().model_dump_json()
        previous = monitor.status_at
        stack.stop("one")
        await monitor.refresh()
        assert monitor.status_error == "UNREACHABLE"
        assert not monitor.overview().status_available
        assert monitor.status_at == previous and monitor.status.tools == 5
        stack.start("one")
        await monitor.refresh()
        assert monitor.overview().status_available
        assert monitor.overview().gateway.ready
    finally:
        await monitor.close()
        stack.close()
