import pytest
from jsonschema import Draft202012Validator
from mcp import Client

from mcp_stack.wire import GATEWAY_META

pytestmark = pytest.mark.integration


async def test_complete_scientific_contract_passes_through_without_domain_coupling(live_stack):
    server = live_stack.config.enabled_servers[0]
    async with Client(server.transport.url, cache=None) as direct:
        downstream_tools = {tool.name: tool for tool in (await direct.list_tools()).tools}
        async with Client(live_stack.url, cache=None) as gateway:
            upstream_tools = {tool.name: tool for tool in (await gateway.list_tools()).tools}
            for name, arguments in [
                ("demo.identity_matrix", {"size": 3}),
                ("demo.contract_error", {}),
                ("demo.artifact", {}),
            ]:
                assert upstream_tools[name] == downstream_tools[name]
                downstream = await direct.call_tool(name, arguments)
                upstream = await gateway.call_tool(name, arguments)
                assert downstream.content == upstream.content
                assert downstream.structured_content == upstream.structured_content
                assert downstream.is_error == upstream.is_error
                for key, value in downstream.meta.items():
                    assert upstream.meta[key] == value
                assert upstream.meta[GATEWAY_META]["attempts"] == 1
                if not upstream.is_error:
                    Draft202012Validator(upstream_tools[name].output_schema).validate(
                        upstream.structured_content
                    )
            assert gateway.server_capabilities.resources is None
