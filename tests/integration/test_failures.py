import asyncio

import httpx
import pytest
from mcp import Client

from mcp_stack.wire import ERROR_META, GATEWAY_META, INFRA_ERROR_META

pytestmark = pytest.mark.integration


async def test_native_router_domain_errors_and_circuit(live_stack):
    async with Client(live_stack.url, cache=None) as client:
        for _ in range(4):
            result = await client.call_tool("demo.contract_error", {})
            assert result.meta[ERROR_META]["category"] == "domain"
        assert not (await client.call_tool("demo.echo", {"message": "available"})).is_error
        for _ in range(3):
            result = await client.call_tool("demo.slow", {"seconds": 3})
            assert result.meta[INFRA_ERROR_META]["code"] == "CALL_TIMEOUT"
        blocked = await client.call_tool("demo.echo", {"message": "blocked"})
        assert blocked.meta[GATEWAY_META]["attempts"] == 0
        assert blocked.meta[INFRA_ERROR_META]["code"] == "CIRCUIT_OPEN"
        await asyncio.sleep(1.1)
        assert not (await client.call_tool("demo.echo", {"message": "recovered"})).is_error
    async with httpx.AsyncClient() as http:
        response = await http.get(live_stack.admin_url + "/metrics")
        assert "mcp_one_tool_calls_total" in response.text
        status = (await http.get(live_stack.admin_url + "/status")).json()
        assert status["servers"]["mock-scientific-mcp"]["circuit"] == "CLOSED"


async def test_downstream_offline_and_readiness_recovery(live_stack):
    async with Client(live_stack.url, cache=None) as client:
        live_stack.stop("mock")
        try:
            failure = await client.call_tool("demo.echo", {"message": "offline"})
            assert failure.meta[INFRA_ERROR_META]["category"] == "infrastructure"
            async with httpx.AsyncClient() as http:
                assert (await http.get(live_stack.admin_url + "/health")).status_code == 200
                assert (await http.get(live_stack.admin_url + "/ready")).status_code == 503
        finally:
            live_stack.start("mock")
        async with httpx.AsyncClient() as http:
            for _ in range(30):
                await http.post(live_stack.admin_url + "/refresh")
                if (await http.get(live_stack.admin_url + "/ready")).status_code == 200:
                    break
                await asyncio.sleep(0.2)
            else:
                pytest.fail("gateway did not recover")
        assert not (await client.call_tool("demo.echo", {"message": "online"})).is_error
