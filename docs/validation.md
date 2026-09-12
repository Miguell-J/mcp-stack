# Native stack validation

Executed 2026-09-11 and rechecked 2026-09-12, Linux x86_64, host Python 3.14.3
and containers Python 3.12.12.
The old four-process deployment was stopped and its gateway-edge/legacy-bridge
containers removed. The actual replacement path is:

```text
SDK client / Codex configuration
        -> MCP One :8765/mcp
        -> mock-scientific-mcp (internal network)
```

The dependency is the official clean MCP One commit
`4f1b54e563c12cd71f0ca3490d140b2e42b734ad`, version 1.0.0rc1. Bootstrap fetched
that commit from the official URL, checked origin/cleanliness, compiled/imported
the native package and installed its own locked dependencies without source edits.
MCP One's [remote CI passed](https://github.com/Miguell-J/mcp-one/actions/runs/34644211632)
on Python 3.12/3.14 and Docker. Its [PR](https://github.com/Miguell-J/mcp-one/pull/6)
contains the migration and standalone validation record.

| Check | Observed result |
| --- | --- |
| Stack full local pytest suite against the clean pin | 60 passed, one third-party warning, 24.40 s |
| Scientific adapter template | 1 passed, 0.59 s |
| Native gateway standalone | 62 passed on Python 3.14 and Python 3.12; 91.28% coverage |
| Ruff / format / strict mypy | Passed; stack mypy covers 23 source files |
| Native runtime, stack runtime, dev runner and template builds | Passed |
| Host SDK client against Docker endpoint | 6 E2E passed, 0.69 s |
| Python 3.12 SDK client inside Docker | 6 E2E passed, 1.07 s |
| Docker mock stop/restart | Readiness 503 + infrastructure isError; recovery to 200 + successful call |
| Template non-root/read-only app factory | Passed, UID 10001 |
| All Compose profiles config validation | Passed |
| Optional collector | Actual OTLP trace batches received, including 3/4-span batches during native discovery |
| Codex CLI 0.154.0 | add, list and get --json succeeded using a temporary CODEX_HOME |

Repeated E2E runs are the same six scenarios, not extra unique tests. The warning
comes from Starlette's deprecated AnyIO BlockingPortal alias, not a deprecated MCP
API in this project. Restricted sandbox IPC stalled the first template attempt;
it was interrupted and rerun successfully with local IPC available. Docker used
its classic builder fallback because the local host lacks buildx; CI installs it.

The first remote stack integration run exposed test references to the removed
gateway.one_url config field after the final legacy-field cleanup. The fixtures
now derive their admin URL from the actual test listener; the native gateway/pin
did not change. That failed run is retained in Actions history, and the complete
suite was rerun before publishing the correction.

`make health` reports `mcp-stack ready` and `mock-scientific-mcp ONLINE`.
`make tools` obtains native tools/list and returns demo.artifact,
demo.contract_error, demo.echo, demo.identity_matrix and demo.slow.

The contract tests compare direct/routed definitions and identity_matrix,
contract_error and artifact results: content, structuredContent, isError, every
original metadata key, concrete outputSchema, ScientificResult diagnostics and
provenance, including the untouched artifact reference. MCP One imports no
scientific contract package. Real SDK tests also verify server/discover,
Mcp-Method, Mcp-Name, MCP-Protocol-Version, no session ID in modern calls, private
TTL zero, unknown tools, invalid arguments, malformed requests and free SDK legacy
handshake compatibility. Fault tests cover timeouts, circuits, recovery and invalid
catalogs/results. The gateway's separate adversarial review covers duplicate
execution, cookie isolation, metadata collisions, cancellation and auth errors.

## Benchmark

Raw observations are in [native-benchmark.json](native-benchmark.json). Ten warmups
per path, then 100 sequential calls each in alternating order; nearest-rank p95.

| Path | Median | p95 |
| --- | --- | --- |
| SDK client -> mock | 4.398 ms | 5.929 ms |
| SDK client -> MCP One -> mock | 10.314 ms | 14.949 ms |

The difference between medians was 5.916 ms. This is a development smoke test,
not a load benchmark, scientific study or production latency guarantee. The
benchmark ran temporary real HTTP processes and always shut them down.

## Commands executed

```bash
python3 scripts/bootstrap.py --update-dependency
make lint
.venv/bin/python -m pytest -xq
make test-template contract-docs
make down
make up
make health tools codex-config
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
make fault-check
docker compose --profile core --profile dev build test-runner
docker compose --profile core --profile dev run --rm test-runner
docker build -f templates/python_scientific_mcp/Dockerfile -t example-scientific-mcp:0.1.0 .
docker compose --profile core --profile dev --profile observability config --quiet
```

The optional collector was enabled by setting
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces for
`docker compose --profile core --profile observability up -d --wait` and its
received batches were checked with `logs`. Codex commands ran in a temporary
directory, which was deleted afterwards; no user config or credentials were copied.
The CLI's add/list/get checks prove registration, while SDK E2E proves execution.
No authenticated Codex model conversation is claimed.

## Release boundaries

MCP One is a 1.0.0rc1 candidate, reflecting the breaking replacement of 0.1 REST.
Stack configuration is versioned 0.2.0; scientific contract v1 stays unchanged.
The native migration was merged through MCP One PR 6 and mcp-stack PR 1. Main-branch
CI passed for both repositories. MCP One published `v1.0.0-rc.1`; a stable 1.0 release
is not claimed. This record describes the native migration at stack 0.2.0; the
subsequent stack 0.3.0 adds the optional local dashboard without changing the gateway pin.

Tools-only federation excludes resource retrieval, tasks, sampling, elicitation,
continuations, stdio and distributed state. Result caching is absent. Local bearer
authentication is supported; public OAuth deployment is a separate integration.
IPv6 rendering has unit tests; Docker deployment was exercised on IPv4 loopback.
Historical failures and adapter evidence remain isolated under docs/history.
