import os

import httpx
import httpx2
import pytest
from jsonschema import Draft202012Validator
from mcp import Client, MCPError
from mcp.client.streamable_http import streamable_http_client
from mcp.types import ResourceLink, TextContent

from mcp_stack.wire import ERROR_META, GATEWAY_META, INFRA_ERROR_META

pytestmark = pytest.mark.e2e


def headers():
    token = os.getenv("MCP_STACK_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def test_native_discovery_call_and_full_envelope(endpoint):
    async with httpx2.AsyncClient(headers=headers(), trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http), cache=None) as client:
            assert client.protocol_version == "2026-07-28"
            listed = await client.list_tools()
            assert listed.ttl_ms == 0
            tools = {t.name: t for t in listed.tools}
            assert "demo.identity_matrix" in tools
            result = await client.call_tool("demo.identity_matrix", {"size": 3})
            assert not result.is_error
            assert isinstance(result.content[0], TextContent)
            assert result.content[0].text == "Identity fixture of size 3."
            Draft202012Validator(tools["demo.identity_matrix"].output_schema).validate(
                result.structured_content
            )
            assert result.structured_content["data"]["matrix"]["shape"] == [3, 3]
            assert result.structured_content["diagnostics"]["checks"][0]["status"] == "passed"
            assert result.structured_content["provenance"]["deterministic"] is True
            metadata = result.meta[GATEWAY_META]
            assert metadata["server"] == "mock-scientific-mcp"
            assert metadata["tool"] == "demo.identity_matrix"
            assert metadata["attempts"] == 1 and metadata["cached"] is False
            assert len(metadata["traceId"]) == 32 and metadata["durationMs"] > 0
            # Integration tests also inspect MCP One's native router metrics.
            echoed = await client.call_tool("demo.echo", {"message": "scientific-stack"})
            assert echoed.structured_content["data"]["message"] == "scientific-stack"
            assert (
                echoed.meta["io.github.miguell-j.mock/trace"]["traceId"]
                == echoed.meta[GATEWAY_META]["traceId"]
            )
            assert "success" not in result.model_dump(by_alias=True)


async def test_domain_error_and_artifact_reference(endpoint):
    async with httpx2.AsyncClient(headers=headers(), trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http), cache=None) as client:
            await client.list_tools()
            failure = await client.call_tool("demo.contract_error", {})
            assert failure.is_error is True
            assert failure.structured_content is None
            assert failure.meta[ERROR_META]["category"] == "domain"
            assert failure.meta[ERROR_META]["code"] == "INVALID_DOMAIN"
            assert failure.meta[GATEWAY_META]["attempts"] == 1
            artifact = await client.call_tool("demo.artifact", {})
            assert isinstance(artifact.content[1], ResourceLink)
            assert artifact.structured_content["data"]["artifact"]["sha256"]


async def test_unknown_tool_and_invalid_arguments(endpoint):
    async with httpx2.AsyncClient(headers=headers(), trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http), cache=None) as client:
            await client.list_tools()
            with pytest.raises(MCPError) as error:
                await client.call_tool("demo.missing", {})
            assert error.value.code == -32602
            invalid = await client.call_tool("demo.identity_matrix", {"size": 999})
            assert invalid.is_error
            assert invalid.meta[INFRA_ERROR_META]["code"] == "INVALID_ARGUMENT"
            assert invalid.meta[GATEWAY_META]["attempts"] == 0


async def test_malformed_protocol_and_header_mismatch(endpoint):
    async with httpx.AsyncClient(headers=headers(), trust_env=False) as client:
        malformed = await client.post(
            endpoint,
            content=b"{invalid",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert malformed.status_code == 400
        mismatch = await client.post(
            endpoint,
            headers={
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/call",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}},
            },
        )
        assert mismatch.status_code == 400


async def test_legacy_client_compatibility_via_sdk(endpoint):
    async with httpx2.AsyncClient(headers=headers(), trust_env=False) as http:
        async with Client(
            streamable_http_client(endpoint, http_client=http), mode="legacy"
        ) as client:
            assert client.protocol_version != "2026-07-28"
            await client.list_tools()
            result = await client.call_tool("demo.echo", {"message": "legacy-compatible"})
            assert result.structured_content["data"]["message"] == "legacy-compatible"


async def test_sdk_emits_current_protocol_headers(endpoint):
    sent = []

    async def observe(request):
        if request.method == "POST":
            sent.append(dict(request.headers))

    async with httpx2.AsyncClient(
        headers=headers(), trust_env=False, event_hooks={"request": [observe]}
    ) as http:
        async with Client(streamable_http_client(endpoint, http_client=http), cache=None) as client:
            await client.list_tools()
            await client.call_tool("demo.echo", {"message": "headers"})
    assert any(h.get("mcp-method") == "server/discover" for h in sent)
    call = next(h for h in sent if h.get("mcp-method") == "tools/call")
    assert call["mcp-name"] == "demo.echo"
    assert call["mcp-protocol-version"] == "2026-07-28"
    assert "mcp-session-id" not in call
