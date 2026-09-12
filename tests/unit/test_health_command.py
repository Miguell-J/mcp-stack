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


@pytest.mark.parametrize("status", [200, 401, 503])
async def test_readiness_wait_handles_startup_auth_and_deadline(monkeypatch, status):
    original_client = httpx.AsyncClient
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"ready": calls > 1, "servers": {}})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        health.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    assert await health.main(wait_seconds=0.02) == (0 if status == 200 else 1)
    if status == 401:
        assert calls == 1  # Authentication errors are terminal, not discovery delays.
    else:
        assert calls >= 2
