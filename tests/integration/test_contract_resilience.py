import httpx
import pytest
from jsonschema import Draft202012Validator
from mcp import Client
from scientific_mcp_contracts import ScientificError, ScientificResult

from mcp_stack.wire import ERROR_META, GATEWAY_META
from services.mock_scientific_mcp.app import EchoData

pytestmark = pytest.mark.integration


async def test_repeated_domain_errors_preserve_provenance_and_do_not_trip_circuit(live_stack):
    async with Client(live_stack.url, cache=None) as gateway:
        tools = {tool.name: tool for tool in (await gateway.list_tools()).tools}
        for _ in range(live_stack.config.gateway.circuit_breaker_failures + 1):
            result = await gateway.call_tool("demo.contract_error", {})
            assert result.is_error
            assert result.meta[GATEWAY_META]["attempts"] == 1
            error = ScientificError.model_validate(result.meta[ERROR_META])
            assert error.code == "INVALID_DOMAIN" and error.category == "domain"
            assert error.retryable is False
        result = await gateway.call_tool("demo.echo", {"message": "after-domain-errors"})
        assert not result.is_error
        Draft202012Validator(tools["demo.echo"].output_schema).validate(result.structured_content)
        typed = ScientificResult[EchoData].model_validate(result.structured_content)
        assert typed.data.message == "after-domain-errors"
        assert typed.provenance.library == "mock-fixture"
        assert typed.provenance.deterministic is True
    async with httpx.AsyncClient(trust_env=False) as http:
        status = (await http.get(live_stack.admin_url + "/status")).json()
    assert all(server["circuit"] == "CLOSED" for server in status["servers"].values())
