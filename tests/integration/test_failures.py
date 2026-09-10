import asyncio

import httpx
import pytest
from mcp import Client

from mcp_stack.wire import ERROR_META, GATEWAY_META

pytestmark = pytest.mark.integration


async def test_real_router_metrics_domain_errors_and_circuit(live_stack):
    base = live_stack.config.gateway.one_url
    async with httpx.AsyncClient() as http:
        before = (await http.get(base + "/metrics")).json()["call_requests_total"]
        async with Client(live_stack.url, cache=None) as client:
            await client.list_tools()
            for _ in range(4):
                result = await client.call_tool("demo.contract_error", {})
                assert result.meta[ERROR_META]["category"] == "domain"
            success = await client.call_tool("demo.echo", {"message": "still available"})
            assert not success.is_error
            for _ in range(3):
                timeout = await client.call_tool("demo.slow", {"seconds": 3})
                assert timeout.is_error
                assert timeout.meta[ERROR_META]["code"] == "TIMEOUT"
                assert timeout.meta[ERROR_META]["category"] == "infrastructure"
            blocked = await client.call_tool("demo.echo", {"message": "circuit open"})
            assert blocked.meta[GATEWAY_META]["attempts"] == 0
            assert blocked.meta[ERROR_META]["code"] == "DOWNSTREAM_UNAVAILABLE"
            await asyncio.sleep(1.1)
            recovered = await client.call_tool("demo.echo", {"message": "recovered"})
            assert recovered.structured_content["data"]["message"] == "recovered"
        metrics = (await http.get(base + "/metrics")).json()
        assert metrics["call_requests_total"] - before == 10
        assert metrics["open_circuits"] == 0


async def test_downstream_offline_and_health_recovery(live_stack):
    async with Client(live_stack.url, cache=None) as client:
        await client.list_tools()
        live_stack.stop("mock")
        try:
            async with httpx.AsyncClient() as http:
                unhealthy = await http.get(live_stack.url.removesuffix("/mcp") + "/health")
                assert unhealthy.status_code == 503
                assert unhealthy.json()["services"]["mock-scientific-mcp"] == "unhealthy"
                await http.post(live_stack.config.gateway.one_url + "/servers/refresh")
            failure = await client.call_tool("demo.echo", {"message": "offline"})
            assert failure.meta[ERROR_META]["category"] == "infrastructure"
            assert failure.meta[ERROR_META]["code"] == "DOWNSTREAM_UNAVAILABLE"
        finally:
            live_stack.start("mock")
        await client.list_tools()
        result = await client.call_tool("demo.echo", {"message": "online again"})
        assert not result.is_error
        async with httpx.AsyncClient() as http:
            healthy = await http.get(live_stack.url.removesuffix("/mcp") + "/health")
            assert healthy.status_code == 200


async def test_hub_offline_is_an_infrastructure_failure(live_stack):
    async with Client(live_stack.url, cache=None) as client:
        await client.list_tools()
        live_stack.stop("one")
        try:
            result = await client.call_tool("demo.echo", {"message": "hub offline"})
            assert result.is_error
            assert result.meta[ERROR_META]["category"] == "infrastructure"
            assert result.meta[ERROR_META]["code"] == "DOWNSTREAM_UNAVAILABLE"
            assert "attempts" not in result.meta[GATEWAY_META]
        finally:
            live_stack.start("one")
        await client.list_tools()
        assert not (await client.call_tool("demo.echo", {"message": "hub recovered"})).is_error
