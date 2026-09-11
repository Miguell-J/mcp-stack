import httpx
import pytest

from scripts import health


@pytest.mark.parametrize("status", [200, 401, 503])
async def test_health_command_handles_admin_rejection_without_unbound_data(monkeypatch, status):
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, json={"ready": True, "servers": {}})
    )
    monkeypatch.setattr(
        health.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    assert await health.main() == (0 if status == 200 else 1)
