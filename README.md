# mcp-stack

Composition and operation of independent scientific MCP servers. MCP One provides
the native gateway, registry, routing and failure policy. The stack owns manifests,
scientific contracts, fixtures and deployment. Version **0.3.0**, Scientific MCP
Contract **v1**, MCP **2026-07-28**, official Python SDK **2.2.0**.

```text
Codex / MCP SDK client
          |
   MCP One :8765/mcp
          |
 mock-scientific-mcp /mcp
```

No gateway-edge, legacy-bridge or REST execution adapter is required. The clean
upstream source is pinned by full commit in config/stack.yaml and built using its
own Dockerfile and lock. Scientific libraries do not depend on the gateway.

## Start

Requires Git, Make, Python 3.12–3.14, Docker and Compose with include support.

```bash
make bootstrap
make up
make health
make tools
make test-e2e
make codex-config
```

Open **[the local monitor](http://127.0.0.1:8766)** after `make up`. It shows gateway
readiness, server/circuit states, a searchable native tool catalog and live metrics.
Light/dark themes, request/response schema modals, throughput/latency/error charts
and per-server performance indicators are included.
The dashboard is read-only; disabled library manifests appear as pending integrations.
See [Dashboard](docs/dashboard.md) for configuration, security and signal semantics.

Endpoint: `http://127.0.0.1:8765/mcp`, directly served by MCP One. Expected tools:
demo.echo, demo.identity_matrix, demo.contract_error, demo.slow and demo.artifact.
These are integration fixtures. To test the actual running containers:

```bash
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
make fault-check
make down
```

Bootstrap refuses dirty or differently pinned dependencies. An intentional pin
migration uses `python3 scripts/bootstrap.py --update-dependency` after reviewing
the candidate. It verifies the official origin, exact commit, compilation and
native import, and installs each repository's own committed dependency lock.

## Development

```bash
make validate render
make lint test test-contract test-template
make test-integration test-e2e
make logs
make restart
```

Edit config/stack.yaml and config/servers.d/*.yaml, then make render. Generated
Compose/native config is ignored; the generated JSON Schema is checked for drift.
The stack does not copy, patch or reimplement MCP One. `MCP_ONE_SOURCE` is an
explicit subprocess-test-only override for upstream development, not a production
bootstrap/build override. Final validation must use the pinned clean checkout.

[Architecture](docs/architecture.md) · [Quickstart](docs/quickstart.md) ·
[Add a server](docs/adding-a-server.md) · [Codex](docs/codex-integration.md) ·
[Compatibility](docs/protocol-compatibility.md) · [Native migration](docs/mcp-one-upgrade-path.md) ·
[Observability](docs/observability.md) · [Security](docs/security.md) ·
[Troubleshooting](docs/troubleshooting.md) · [Scientific contract](docs/contracts/scientific-result-v1.md) ·
[Validation](docs/validation.md).
