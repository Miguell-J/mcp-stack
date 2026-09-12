import pytest
from starlette.testclient import TestClient

from services.mock_scientific_mcp.app import create_app


@pytest.mark.parametrize(
    "header,value", [("Host", "attacker.invalid"), ("Origin", "https://attacker.invalid")]
)
def test_fixture_dns_rebinding_and_origin_protection(header, value):
    with TestClient(create_app(), base_url="http://localhost") as client:
        response = client.post("/mcp", json={}, headers={header: value})
        assert response.status_code in {403, 421}
