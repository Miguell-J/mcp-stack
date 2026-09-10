# Validation record

Executed on 2026-09-10, Linux x86_64. Host Python 3.14.3; runtime and development
containers Python 3.12.12. These are observations from real execution, not
expected example output. Remote CI status is reported separately by GitHub Actions.

## Results

| Check | Actual result |
| --- | --- |
| Full local `python -m pytest -q` | 64 passed, 1 third-party deprecation warning, 34.80 s |
| Thin adapter `make test-template` | 1 passed, 0.51 s |
| Host SDK client against Docker stack | 6 E2E passed, 6.19 s |
| Python 3.12 SDK client in dev container | 6 E2E passed, 6.59 s |
| Ruff check / format check | Passed |
| Strict mypy | No issues in 26 source files |
| Compose validation, all three profiles | Passed |
| Runtime, MCP One, dev and template image builds | Passed |
| Template import and app factory in non-root, read-only container | Passed |
| Docker stop/start fault check | Health 503 + infrastructure isError, then health 200 + successful call |
| Optional OTel Collector | Started; real OTLP trace batches received, including 45, 51 and 17 spans |
| Codex configuration generator | Endpoint, add command, list command and TOML printed without editing user config |

The warning is Starlette's use of the deprecated AnyIO BlockingPortal alias,
not use of a deprecated MCP API by this project. A sandboxed in-process SDK
test stalled on restricted IPC; it was terminated and rerun successfully outside
the sandbox. Local integration tests require permission to bind loopback sockets.

The E2E counts above are repeated executions of the same six scenarios on
different topologies, not additional unique test cases. The template adds one
independent test beyond the 64-test root suite.

## Acceptance evidence

`make health` against the published Docker endpoint returned:

```text
mcp-stack healthy
native MCP edge healthy
mcp-one healthy
mock-scientific-mcp healthy
```

`make tools` queried native tools/list and returned:

```text
demo
  demo.artifact
  demo.contract_error
  demo.echo
  demo.identity_matrix
  demo.slow
```

The real SDK E2E verifies server/discover, protocol 2026-07-28, Mcp-Method,
Mcp-Name, MCP-Protocol-Version, no session ID in modern mode, legacy-mode
compatibility, TTL zero, concrete outputSchema validation, human content,
structuredContent, diagnostics, provenance, isError and namespaced metadata.
The mock and edge report the same W3C trace ID. Integration tests additionally
inspect MCP One's actual routed-call metrics to prove the original router was used.

Domain errors do not trip the original circuit breaker. Repeated infrastructure
timeouts open it; a later attempt after the configured reset succeeds. Tests also
stop and restore both the mock and hub; inject invalid runtime output, invalid
schemas, external schema references and duplicate normalized names; and test
unknown tools, malformed JSON, mismatched method headers and invalid arguments.

## Upstream evidence

The default MCP One commit 9e938ed51bd1aa3ccea94b99a1b045ba446e3eea fails
compilation/import with IndentationError and cannot collect its original tests.
The pinned, unmodified dafd1e1ed681a05f2dc7ea0c0e7ab796036c9689 compiles and
imports. Its original suite returned 6 passed, 2 failed, 8 warnings; both failed
tests use incomplete AsyncMock HTTP response mocks. Native /mcp discovery on
that original FastAPI app returned HTTP 404. See the detailed integration audit.

No upstream fixes were made, and those two upstream tests are not counted as
passing stack tests. CRR and the future scientific domain libraries are untouched.

## Operational findings and limits

The initial Docker run exposed two real issues that were corrected: several
services concurrently building the same image tag, and a port binding that Docker
did not publish from an internal-only network. There is now one runtime image
builder and an edge-only entrance network; regression assertions cover both.
The local machine lacks buildx, so its successful builds used Docker's classic
fallback with a deprecation warning. CI explicitly installs buildx.

Only the IPv4 loopback deployment was exercised in Docker. IPv6 endpoint and
Compose rendering have unit assertions, not a host IPv6 deployment claim.
Codex CLI 0.154.0 help was checked, but the stack was not registered in the user's
Codex configuration and no Codex conversation was used as a substitute for SDK E2E.
The collector is a development console exporter, not persistent trace storage.
Resources are referenced, not federated by the tools-only edge. Remote/public
OAuth deployments, distributed rate limiting and scientific result caching are
outside this MVP. MCP One's own Prometheus response and native protocol support
still require upstream changes documented in the upgrade path.

## Reproduce

```bash
make bootstrap
make lint test test-template
make test-integration test-e2e
docker compose --profile core --profile dev --profile observability config --quiet
make up
make health tools codex-config
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
make fault-check
docker compose --profile core --profile dev build test-runner
docker compose --profile core --profile dev run --rm test-runner
docker build -f templates/python_scientific_mcp/Dockerfile -t example-scientific-mcp:0.1.0 .
make down
```
