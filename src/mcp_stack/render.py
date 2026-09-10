"""Render legacy YAML and Compose from the same validated manifests."""

import json
import math
from pathlib import Path
from typing import Any

import yaml

from mcp_stack.config import StackConfig

GENERATED = "# GENERATED FILE - DO NOT EDIT. Run make render.\n"


def one_config(config: StackConfig) -> dict[str, Any]:
    gateway = config.gateway
    return {
        "servers": [
            {
                "name": s.namespace,
                "url": gateway.bridge_url,
                "enabled": True,
                "description": s.display_name,
                "timeout": math.ceil(s.transport.timeout_seconds + 1),
                "retry_attempts": gateway.health_retry_attempts,
                "circuit_breaker_failures": gateway.circuit_breaker_failures,
                "circuit_breaker_reset_seconds": gateway.circuit_breaker_reset_seconds,
                "endpoints": {key: f"/servers/{s.id}/{key}" for key in ("health", "tools", "call")},
                "response_map": {
                    "tools_key": "tools",
                    "tool_name_field": "name",
                    "tool_desc_field": "description",
                },
                "payload_map": {"tool_field": "tool", "args_field": "invocation"},
            }
            for s in config.enabled_servers
        ],
        "hub": {
            "host": "0.0.0.0",
            "port": 8000,
            "debug": False,
            "log_level": "INFO",
            "cors_enabled": False,
        },
        "cache": {"enabled": False},
        "rate_limit": {"enabled": True, "requests_per_minute": gateway.rate_limit_per_minute},
    }


def probe(url: str) -> dict[str, Any]:
    return {
        "test": [
            "CMD",
            "python",
            "-c",
            f"import urllib.request; urllib.request.urlopen('{url}', timeout=10)",
        ],
        "interval": "10s",
        "timeout": "12s",
        "retries": 3,
        "start_period": "20s",
    }


def compose_config(config: StackConfig) -> dict[str, Any]:
    bind = f"[{config.gateway.bind}]" if ":" in config.gateway.bind else config.gateway.bind
    common: dict[str, Any] = {
        "image": "mcp-stack:0.1.0",
        "profiles": ["core"],
        "networks": ["scientific"],
        "user": "10001:10001",
        "read_only": True,
        "tmpfs": ["/tmp:size=32m,mode=1777"],
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "init": True,
        "stop_grace_period": "20s",
        "restart": "unless-stopped",
        "environment": {
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-}"
        },
    }
    services: dict[str, Any] = {}
    for server in config.enabled_servers:
        if server.container:
            service = {
                **common,
                "image": server.container.image,
                "command": server.container.command,
                "healthcheck": probe(f"http://127.0.0.1:{server.container.port}/health"),
            }
            if server.container.image == common["image"]:
                service["pull_policy"] = "never"
            services[server.id] = service
    mounted = ["./config:/app/config:ro"]
    bridge_environment = dict(common["environment"])
    for server in config.enabled_servers:
        if server.transport.token_env:
            key = server.transport.token_env
            bridge_environment[key] = "${" + key + ":?downstream token is required}"
    services["legacy-bridge"] = {
        **common,
        "pull_policy": "never",
        "volumes": mounted,
        "environment": bridge_environment,
        "command": [
            "uvicorn",
            "services.gateway_edge.bridge:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--no-access-log",
        ],
        "healthcheck": probe("http://127.0.0.1:8080/live"),
    }
    services["mcp-one"] = {
        **common,
        "image": config.mcp_one.image or f"mcp-one-stack:{config.mcp_one.ref[:12]}",
        "build": {
            "context": ".",
            "dockerfile": "services/gateway_edge/Dockerfile",
            "target": "mcp-one",
        },
        "volumes": ["./.generated/mcp-one.yaml:/opt/mcp-one/src/config.yaml:ro"],
        "environment": {**common["environment"], "PYTHONPATH": "/opt/mcp-one/src"},
        "command": [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ],
        "depends_on": {"legacy-bridge": {"condition": "service_healthy"}},
        "healthcheck": probe("http://127.0.0.1:8000/health"),
    }
    if config.mcp_one.image:
        services["mcp-one"].pop("build")
    services["gateway-edge"] = {
        **common,
        "networks": ["entrance", "scientific"],
        "build": {
            "context": ".",
            "dockerfile": "services/gateway_edge/Dockerfile",
            "target": "runtime",
        },
        "volumes": mounted,
        "environment": {**common["environment"], "MCP_STACK_TOKEN": "${MCP_STACK_TOKEN:-}"},
        "command": [
            "uvicorn",
            "services.gateway_edge.edge:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--no-access-log",
        ],
        "ports": [f"{bind}:{config.gateway.port}:8080"],
        "depends_on": {"mcp-one": {"condition": "service_healthy"}},
        "healthcheck": probe("http://127.0.0.1:8080/live"),
    }
    services["test-runner"] = {
        **common,
        "image": "mcp-stack-dev:0.1.0",
        "build": {
            "context": ".",
            "dockerfile": "services/gateway_edge/Dockerfile",
            "target": "development",
        },
        "profiles": ["dev"],
        "restart": "no",
        "read_only": False,
        "environment": {
            "STACK_ENDPOINT": "http://gateway-edge:8080/mcp",
            "MCP_STACK_TOKEN": "${MCP_STACK_TOKEN:-}",
        },
        "command": ["python", "-m", "pytest", "tests/e2e", "-q"],
    }
    services["otel-collector"] = {
        "image": "otel/opentelemetry-collector:0.146.1@sha256:"
        "23f75833cfcf0ebdde9b2e1ba41616b9092294af6947f2feea1b4ebc393030f5",
        "profiles": ["observability"],
        "networks": ["scientific"],
        "user": "10001:10001",
        "read_only": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "volumes": ["./config/otel-collector.yaml:/etc/otelcol/config.yaml:ro"],
        "command": ["--config=/etc/otelcol/config.yaml"],
    }
    return {
        "services": services,
        "networks": {"entrance": {}, "scientific": {"internal": True}},
    }


def render(config: StackConfig, root: Path) -> None:
    output = root / ".generated"
    output.mkdir(exist_ok=True)
    for name, data in (
        ("mcp-one.yaml", one_config(config)),
        ("compose.yaml", compose_config(config)),
    ):
        (output / name).write_text(GENERATED + yaml.safe_dump(data, sort_keys=False))
    schemas = root / "config/schemas"
    schemas.mkdir(exist_ok=True)
    schema = StackConfig.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$comment"] = (
        "GENERATED FILE - DO NOT EDIT. Expanded stack + servers.d model; make render."
    )
    (schemas / "stack.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
