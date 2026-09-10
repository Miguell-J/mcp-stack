import httpx
import pytest
from mcp import Client

from mcp_stack.wire import ERROR_META

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mode", ["duplicate", "schema", "external_ref", "response"])
async def test_faulty_downstream_is_rejected_and_recovers(live_stack, mode):
    state = live_stack.directory / "fault.txt"
    state.write_text(mode)
    live_stack.stop("mock")
    live_stack.env["STACK_FAULT_FILE"] = str(state)
    try:
        live_stack.start("mock")
        async with httpx.AsyncClient() as http:
            bridge = live_stack.config.gateway.bridge_url + "/servers/mock-scientific-mcp"
            if mode != "response":
                assert (await http.get(bridge + "/tools")).status_code == 502
                assert (await http.get(bridge + "/health")).status_code == 503
                async with Client(live_stack.url, cache=None) as client:
                    assert (await client.list_tools()).tools == []
            else:
                async with Client(live_stack.url, cache=None) as client:
                    await client.list_tools()
                    result = await client.call_tool("demo.echo", {"message": "bad output"})
                    assert result.is_error
                    assert result.meta[ERROR_META]["category"] == "infrastructure"
                    assert result.meta[ERROR_META]["code"] == "INTERNAL_ERROR"
    finally:
        live_stack.stop("mock")
        live_stack.env.pop("STACK_FAULT_FILE")
        live_stack.start("mock")
    async with Client(live_stack.url, cache=None) as client:
        assert len((await client.list_tools()).tools) == 5
        assert not (await client.call_tool("demo.echo", {"message": "recovered"})).is_error
