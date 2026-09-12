from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from mcp_stack.config import StackConfig, load_config, local_name, qualified_name
from mcp_stack.render import compose_config, one_config, render


def test_current_config_and_render_reproducibility(tmp_path):
    config = load_config()
    (tmp_path / "config").mkdir()
    render(config, tmp_path)
    first = (tmp_path / ".generated/compose.yaml").read_bytes()
    render(config, tmp_path)
    assert first == (tmp_path / ".generated/compose.yaml").read_bytes()
    assert first.startswith(b"# GENERATED FILE")
    services = compose_config(config)["services"]
    exposed = {k for k, v in services.items() if v.get("ports")}
    assert exposed == {"mcp-one"}
    assert services["mcp-one"]["ports"] == ["127.0.0.1:8765:8000"]
    assert services["mcp-one"]["build"]["target"] == "runtime"
    assert compose_config(config)["networks"]["scientific"]["internal"]
    assert services["mcp-one"]["networks"] == ["entrance", "scientific"]
    assert all(
        "entrance" not in service["networks"]
        for name, service in services.items()
        if name != "mcp-one"
    )
    runtime_builders = [
        s for s in services.values() if s.get("image") == "mcp-stack:0.2.0" and "build" in s
    ]
    assert len(runtime_builders) == 1
    assert "cache" not in one_config(config)
    assert one_config(config)["servers"][0]["namespace"] == "demo"
    assert "legacy-bridge" not in services
    assert "gateway-edge" not in services
    assert config.gateway.endpoint == "http://127.0.0.1:8765/mcp"
    config.gateway.bind = "::1"
    assert config.gateway.endpoint == "http://[::1]:8765/mcp"
    assert compose_config(config)["services"]["mcp-one"]["ports"] == ["[::1]:8765:8000"]


@pytest.mark.parametrize("key", ["id", "namespace"])
def test_duplicate_manifest_rejected(key):
    data = load_config().model_dump()
    data["servers"][1][key] = data["servers"][0][key]
    with pytest.raises(ValidationError, match="duplicate"):
        StackConfig.model_validate(data)


@pytest.mark.parametrize(
    "name,expected",
    [("echo", "demo.echo"), ("demo.echo", "demo.echo"), ("system.echo", "demo.system.echo")],
)
def test_namespace_no_duplicate_prefix(name, expected):
    assert qualified_name("demo", name) == expected
    assert "demo." + local_name("demo", name) == expected


@pytest.mark.parametrize("name", ["bad name", "tool/unsafe", "x" * 130, "Uppercase"])
def test_invalid_tool_names(name):
    with pytest.raises(ValueError):
        qualified_name("demo", name)


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "http://user:secret@host/mcp", "http://host/?token=x"]
)
def test_secret_and_unsupported_urls_rejected(url):
    data = load_config().model_dump()
    data["servers"][0]["transport"]["url"] = url
    with pytest.raises(ValidationError):
        StackConfig.model_validate(data)


def test_config_schema_is_generated_without_drift(tmp_path):
    (tmp_path / "config").mkdir()
    render(load_config(), tmp_path)
    assert (tmp_path / "config/schemas/stack.schema.json").read_bytes() == Path(
        "config/schemas/stack.schema.json"
    ).read_bytes()


def test_adding_server_requires_no_route_changes():
    data = load_config().model_dump()
    added = deepcopy(next(s for s in data["servers"] if s["enabled"]))
    added.update(id="future-mcp", namespace="future")
    data["servers"].append(added)
    config = StackConfig.model_validate(data)
    assert one_config(config)["servers"][1]["namespace"] == "future"
    assert "future-mcp" in compose_config(config)["services"]


def test_mcp_enrollment_does_not_require_rest_health():
    data = load_config().model_dump()
    next(server for server in data["servers"] if server["enabled"]).pop("health")
    config = StackConfig.model_validate(data)
    assert one_config(config)["servers"][0]["timeout"]["health_seconds"] == 2
    assert "healthcheck" not in compose_config(config)["services"][config.enabled_servers[0].id]
