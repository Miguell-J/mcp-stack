"""Render native MCP configuration and Compose from the same validated manifests."""

import json
from pathlib import Path
from typing import Any

import yaml

from mcp_stack.config import StackConfig

GENERATED = "# GENERATED FILE - DO NOT EDIT. Run make render.\n"


def one_config(config: StackConfig) -> dict[str, Any]:
    gateway = config.gateway
    return {
        "version": 1,
        "hub": {
            "host": "0.0.0.0",
            "port": 8000,
            "auth": {"bearer_token_env": gateway.token_env},
            "admin_auth": {"bearer_token_env": gateway.admin_token_env},
        },
        "registry": {
            "refresh_interval_seconds": gateway.refresh_interval_seconds,
            "max_tools": gateway.max_tools,
        },
        "limits": {
            "request_bytes": gateway.max_payload_bytes,
            "response_bytes": gateway.max_payload_bytes,
            "schema_bytes": gateway.max_schema_bytes,
            "schema_depth": gateway.max_schema_depth,
        },
        "servers": [
            {
                "id": s.id,
                "namespace": s.namespace,
                "display_name": s.display_name,
                "transport": {"type": s.transport.type, "url": s.transport.url},
                "auth": {"bearer_token_env": s.transport.token_env},
                "timeout": {
                    "discovery_seconds": s.transport.timeout_seconds,
                    "call_seconds": s.transport.timeout_seconds,
                    "health_seconds": s.health.timeout_seconds if s.health else 2,
                },
                "health": {"interval_seconds": gateway.refresh_interval_seconds},
                "retry": {"discovery_attempts": gateway.discovery_attempts},
                "circuit_breaker": {
                    "failure_threshold": gateway.circuit_breaker_failures,
                    "reset_seconds": gateway.circuit_breaker_reset_seconds,
                },
            }
            for s in config.enabled_servers
        ],
    }


def probe(url: str) -> dict[str, Any]:
    return {
        "test": [
            "CMD",
            "python",
            "-c",
            f"import urllib.request; urllib.request.urlopen({url!r}, timeout=10)",
        ],
        "interval": "10s",
        "timeout": "12s",
        "retries": 3,
        "start_period": "20s",
    }


def compose_config(config: StackConfig) -> dict[str, Any]:
    bind = f"[{config.gateway.bind}]" if ":" in config.gateway.bind else config.gateway.bind
    common: dict[str, Any] = {
        "image": "mcp-stack:0.3.0",
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
            }
            if server.health is not None:
                service["healthcheck"] = probe(server.health.url)
            if server.container.image == common["image"]:
                service["pull_policy"] = "never"
            services[server.id] = service
    environment = dict(common["environment"])
    for key in [
        config.gateway.token_env,
        config.gateway.admin_token_env,
        *(server.transport.token_env for server in config.enabled_servers),
    ]:
        if key:
            environment[key] = "${" + key + ":?MCP token is required}"
    services["mcp-one"] = {
        **common,
        "networks": ["entrance", "scientific"],
        "image": config.mcp_one.image or f"mcp-one-stack:{config.mcp_one.ref[:12]}",
        "build": {"context": "./.deps/mcp-one", "target": "runtime"},
        "volumes": ["./.generated/mcp-one.yaml:/app/config.yaml:ro"],
        "environment": environment,
        "ports": [f"{bind}:{config.gateway.port}:8000"],
        "healthcheck": probe("http://127.0.0.1:8000/health"),
    }
    if config.mcp_one.image:
        services["mcp-one"].pop("build")
    if config.dashboard.enabled:
        dashboard = config.dashboard
        dashboard_bind = f"[{dashboard.bind}]" if ":" in dashboard.bind else dashboard.bind
        dashboard_env = {"STACK_CONFIG": "/app/config/stack.yaml"}
        for key in (config.gateway.admin_token_env, config.gateway.token_env):
            if key:
                dashboard_env[key] = "${" + key + ":?MCP token is required}"
        services["dashboard"] = {
            **common,
            "networks": ["entrance", "scientific"],
            "ports": [f"{dashboard_bind}:{dashboard.port}:8080"],
            "environment": dashboard_env,
            "volumes": ["./config:/app/config:ro"],
            "command": [
                "uvicorn",
                "services.dashboard.app:create_app",
                "--factory",
                "--host",
                "0.0.0.0",
                "--port",
                "8080",
                "--no-access-log",
            ],
            "healthcheck": probe("http://127.0.0.1:8080/health"),
            "pull_policy": "never",
        }
    # Exactly one builder, including deployments with only external downstreams.
    for service in services.values():
        if service["image"] == common["image"]:
            service["build"] = {
                "context": ".",
                "dockerfile": "Dockerfile",
                "target": "runtime",
            }
            service.pop("pull_policy", None)
            break
    services["test-runner"] = {
        **common,
        "image": "mcp-stack-dev:0.3.0",
        "build": {
            "context": ".",
            "dockerfile": "Dockerfile",
            "target": "development",
        },
        "profiles": ["dev"],
        "restart": "no",
        "read_only": False,
        "environment": {
            "STACK_ENDPOINT": "http://mcp-one:8000/mcp",
            "MCP_STACK_TOKEN": "${" + config.gateway.token_env + ":?MCP token is required}"
            if config.gateway.token_env
            else "",
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
