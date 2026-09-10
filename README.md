# mcp-stack

Local-first composition for a personal scientific MCP stack. One native MCP
endpoint for Codex, an unmodified pinned MCP One for routing, and independent
scientific adapters. Version **0.1.0**, Scientific MCP Contract **v1**, native
protocol **2026-07-28**, official Python MCP SDK **2.2.0**.

```text
Codex / MCP client
        |
        v
gateway-edge :8765/mcp  (native MCP)
        |
        v
MCP One                 (original REST registry/router/circuit breaker)
        |
        v
legacy-bridge           (generic REST -> native MCP transport adapter)
        |
        v
mock-scientific-mcp      (native MCP fixture)
```

The two compatibility adapters share `services/gateway_edge/` and one image.
They are temporary: the preferred endpoint belongs inside MCP One upstream.
The gateway contains no geometry, mechanics, variational calculus or CAS code.

## Start

Prerequisites: Git, Make, Python 3.12-3.14 with venv, Docker Engine and Docker
Compose v2.20+ (for `include`). Docker access and initial network downloads are
required. No Redis, database, Kubernetes or Docker socket mount is used.

```bash
git clone https://github.com/Miguell-J/mcp-stack.git
cd mcp-stack
cp .env.example .env
make bootstrap
make up
make health
make tools
make test-e2e
make codex-config
```

The endpoint is `http://127.0.0.1:8765/mcp`. `make codex-config` only prints
configuration; it does not edit your Codex settings. To register it yourself:

```bash
codex mcp add scientific-stack --url http://127.0.0.1:8765/mcp
codex mcp list
```

Expected health: mcp-stack, mcp-one, mock-scientific-mcp and native MCP edge all
healthy. Catalog: `demo.echo`, `demo.identity_matrix`, `demo.contract_error`,
`demo.slow`, `demo.artifact`. These are fixtures, not scientific implementations.

`make test-e2e` starts an isolated local stack by default, avoiding mutations to
a running Compose stack. To test the actual running containers explicitly:

```bash
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
make down
```

## Work on the stack

```bash
make validate            # Pydantic config validation
make render              # regenerate Compose, MCP One YAML and JSON Schema
make test                # unit and scientific contract tests
make test-contract
make test-integration    # real subprocess services, offline/timeout/recovery
make test-e2e            # real SDK client, native HTTP end to end
make lint                # Ruff, formatter check and strict mypy
make format
make logs
make restart
make test-template
```

`config/stack.yaml` and `config/servers.d/*.yaml` are authoritative. Generated
runtime YAML is under `.generated/` and ignored by Git. The checked-in config
schema is generated and checked for drift. `.deps/mcp-one/` is a clean,
gitignored checkout at an immutable upstream commit, never a fork or vendored
source tree. `uv.lock` fixes transitive Python dependencies.

## Important compatibility finding

MCP One's audited default branch does not compile. The stack pins the earlier
unmodified Phase 4 commit `dafd1e1ed681a05f2dc7ea0c0e7ab796036c9689`.
It has REST interfaces on both sides and no native `/mcp` endpoint. Its original
suite has two failing HTTP mock tests. See [the audit](docs/mcp-one-integration.md),
[upgrade path](docs/mcp-one-upgrade-path.md) and [compatibility table](docs/protocol-compatibility.md).

## More

- [Quickstart and profiles](docs/quickstart.md)
- [Architecture](docs/architecture.md) and [ADRs](docs/adr/0001-stack-boundaries.md)
- [Add a server](docs/adding-a-server.md) and [thin Python template](templates/python_scientific_mcp/README.md)
- [Scientific contract](docs/contracts/scientific-result-v1.md)
- [Codex integration](docs/codex-integration.md)
- [Observability](docs/observability.md), [security](docs/security.md), [troubleshooting](docs/troubleshooting.md)
- [Validation evidence](docs/validation.md)
