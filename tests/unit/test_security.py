import httpx
import pytest
from starlette.testclient import TestClient

from mcp_stack.http import RequestPolicy
from services.gateway_edge.edge import create_app


async def test_bearer_token_auth_and_no_secret_echo(monkeypatch):
    monkeypatch.setenv("MCP_STACK_TOKEN", "fixture-secret")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 401
        assert "fixture-secret" not in response.text
        assert (await client.get("/live")).status_code == 200


async def test_chunked_body_limit():
    called = False

    async def application(scope, receive, send):
        nonlocal called
        called = True

    async def chunks():
        yield b"a" * 600
        yield b"b" * 600

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=RequestPolicy(application, 1024)),
        base_url="http://localhost",
    ) as client:
        response = await client.post("/mcp", content=chunks())
        assert response.status_code == 413
        assert not called


@pytest.mark.parametrize(
    "header,value", [("Host", "attacker.invalid"), ("Origin", "https://attacker.invalid")]
)
def test_dns_rebinding_and_origin_protection(header, value, monkeypatch):
    monkeypatch.delenv("MCP_STACK_TOKEN", raising=False)
    with TestClient(create_app(), base_url="http://localhost") as client:
        response = client.post("/mcp", json={}, headers={header: value})
        assert response.status_code in {403, 421}
