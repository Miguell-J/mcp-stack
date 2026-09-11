import asyncio

import httpx
import pytest
from mcp import Client

from mcp_stack.wire import INFRA_ERROR_META

pytestmark = pytest.mark.integration


async def refresh(live_stack):
    # The hub coalesces refresh requests with a one-second minimum interval.
    await asyncio.sleep(1.05)
    async with httpx.AsyncClient() as http:
        return await http.post(live_stack.config.gateway.one_url + "/refresh")


@pytest.mark.parametrize("mode", ["duplicate", "schema", "external_ref", "response"])
async def test_faulty_downstream_is_rejected_and_recovers(live_stack, mode):
    state = live_stack.directory / "fault.txt"
    state.write_text(mode)
    live_stack.stop("mock")
    live_stack.env["STACK_FAULT_FILE"] = str(state)
    try:
        live_stack.start("mock")
        await refresh(live_stack)
        async with Client(live_stack.url, cache=None) as client:
            if mode != "response":
                assert (await client.list_tools()).tools == []
            else:
                result = await client.call_tool("demo.echo", {"message": "bad output"})
                assert result.is_error
                assert result.meta[INFRA_ERROR_META]["code"] == "DOWNSTREAM_PROTOCOL_ERROR"
    finally:
        live_stack.stop("mock")
        live_stack.env.pop("STACK_FAULT_FILE")
        live_stack.start("mock")
        await refresh(live_stack)
    async with Client(live_stack.url, cache=None) as client:
        assert len((await client.list_tools()).tools) == 5
        assert not (await client.call_tool("demo.echo", {"message": "recovered"})).is_error
