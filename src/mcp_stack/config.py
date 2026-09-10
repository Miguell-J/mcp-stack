"""Authoritative configuration model and deterministic namespace rules."""

from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("an absolute HTTP(S) URL is required")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("URLs cannot contain credentials, query parameters or fragments")
    return value.rstrip("/")


class Transport(ConfigModel):
    type: Literal["streamable_http"] = "streamable_http"
    url: str
    timeout_seconds: float = Field(default=5, ge=0.1, le=120)
    token_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    _url = field_validator("url")(safe_url)


class Health(ConfigModel):
    url: str
    timeout_seconds: float = Field(default=2, ge=0.1, le=30)
    _url = field_validator("url")(safe_url)


class Contract(ConfigModel):
    family: Literal["scientific-result"] = "scientific-result"
    version: Literal[1] = 1


class Container(ConfigModel):
    image: str = "mcp-stack:0.1.0"
    command: list[str] = Field(min_length=1)
    port: int = Field(default=8080, ge=1024, le=65535)
    profile: Literal["core", "dev"] = "core"

    @field_validator("image")
    @classmethod
    def pinned_image(cls, value: str) -> str:
        if ":" not in value.rsplit("/", 1)[-1] or value.endswith(":latest"):
            raise ValueError("container images require an explicit version or digest")
        return value


class ServerManifest(ConfigModel):
    id: Identifier
    enabled: bool = False
    display_name: str
    namespace: Identifier
    transport: Transport
    health: Health
    contract: Contract = Field(default_factory=Contract)
    metadata: dict[str, str] = Field(default_factory=dict)
    container: Container | None = None


class Dependency(ConfigModel):
    url: Literal["https://github.com/Miguell-J/mcp-one.git"]
    ref: str = Field(pattern=r"^[0-9a-f]{40}$")
    image: str | None = None

    @field_validator("image")
    @classmethod
    def pinned_image(cls, value: str | None) -> str | None:
        if value is not None and (":" not in value.rsplit("/", 1)[-1] or value.endswith(":latest")):
            raise ValueError("upstream image must be versioned")
        return value


class Gateway(ConfigModel):
    bind: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    one_url: str = "http://mcp-one:8000"
    bridge_url: str = "http://legacy-bridge:8080"
    request_timeout_seconds: float = Field(default=15, ge=1, le=180)
    max_payload_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    max_schema_bytes: int = Field(default=131072, ge=1024, le=1048576)
    max_tools: int = Field(default=256, ge=1, le=2048)
    max_schema_depth: int = Field(default=32, ge=4, le=64)
    catalog_ttl_seconds: int = Field(default=0, ge=0, le=60)
    health_retry_attempts: int = Field(default=1, ge=1, le=3)
    circuit_breaker_failures: int = Field(default=3, ge=1, le=100)
    circuit_breaker_reset_seconds: int = Field(default=5, ge=1, le=300)
    rate_limit_per_minute: int = Field(default=600, ge=30, le=10000)
    _urls = field_validator("one_url", "bridge_url")(safe_url)

    @property
    def endpoint(self) -> str:
        host = f"[{self.bind}]" if ":" in self.bind else self.bind
        return f"http://{host}:{self.port}/mcp"


class StackConfig(ConfigModel):
    version: Literal[1] = 1
    protocol: Literal["2026-07-28"] = "2026-07-28"
    mcp_one: Dependency
    gateway: Gateway = Field(default_factory=Gateway)
    servers: list[ServerManifest] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_servers(self) -> Self:
        for key in ("id", "namespace"):
            values = [getattr(s, key) for s in self.servers]
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate server {key}")
        for s in self.servers:
            if s.id in {
                "gateway-edge",
                "legacy-bridge",
                "mcp-one",
                "test-runner",
                "otel-collector",
            }:
                raise ValueError("server ID is reserved for infrastructure")
            if (
                s.enabled
                and self.gateway.request_timeout_seconds <= s.transport.timeout_seconds + 2
            ):
                raise ValueError("gateway timeout must exceed downstream timeout by more than 2s")
            if s.enabled and s.container and s.container.profile != "core":
                raise ValueError("enabled managed servers must use core profile")
        return self

    @property
    def enabled_servers(self) -> list[ServerManifest]:
        return [s for s in self.servers if s.enabled]


def load_config(path: Path = Path("config/stack.yaml")) -> StackConfig:
    if path.stat().st_size > 1_048_576:
        raise ValueError("configuration is too large")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or "servers" in data:
        raise ValueError("stack.yaml must be a mapping; servers belong in servers.d")
    manifests = []
    for manifest in sorted((path.parent / "servers.d").glob("*.yaml")):
        if manifest.stat().st_size > 65536:
            raise ValueError(f"manifest too large: {manifest.name}")
        manifests.append(yaml.safe_load(manifest.read_text()))
    return StackConfig.model_validate({**data, "servers": manifests})


def qualified_name(namespace: str, name: str) -> str:
    import re

    prefix = f"{namespace}."
    full = name if name.startswith(prefix) else prefix + name
    if not re.fullmatch(r"[a-z][a-z0-9_-]*\.[a-z][a-z0-9_.-]*", full) or len(full) > 128:
        raise ValueError("invalid scientific tool name")
    return full


def local_name(namespace: str, name: str) -> str:
    return qualified_name(namespace, name)[len(namespace) + 1 :]
