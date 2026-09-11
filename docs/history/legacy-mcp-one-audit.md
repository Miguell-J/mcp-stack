> Historical record of the pre-native topology. Superseded by ADR 0007.

# MCP One audit

Audited 2026-09-10 from the actual repository, not just its README.

## Revisions and empirical results

- Default branch HEAD: `9e938ed51bd1aa3ccea94b99a1b045ba446e3eea`.
  `python -m compileall -q src tests` and `import app.main` fail with
  `IndentationError` at main.py:162 (empty duplicate lifespan at line 158).
  Original pytest suite aborts collection with the same error.
- Selected unmodified upstream commit:
  `dafd1e1ed681a05f2dc7ea0c0e7ab796036c9689` (Phase 4).
  Compilation and import succeed. Original suite: **6 passed, 2 failed**,
  8 warnings, Python 3.14.3. Failures are `test_list_tools` and
  `test_execute_tool_success`: AsyncMock makes synchronous response.json()
  a coroutine. There are also incomplete MagicMock configuration objects.
  The stack supplies independent integration tests using actual HTTP responses.
- FastAPI TestClient POST `/mcp` with `server/discover`: **404** on the pin.
  Its route table has REST endpoints only. No MCP SDK dependency or MCP transport
  exists in its implementation. It is not a native MCP server for Codex.

## Implementation findings

`src/app/models/schemas.py` accepts YAML server endpoints and payload/response
mappings. Tools retain only name, description, parameters, server_name and
full_name. The registry always prefixes `server_name + '.' + tool.name`.
`inputSchema`, `outputSchema`, annotations and tool metadata otherwise disappear.

`src/app/core/registry.py` GETs health and tools endpoints, retries **health**
requests, and refreshes every 60 seconds. Tool discovery errors are logged but
do not reliably change the online status. Failed health does not evict old tools.
Duplicate tools overwrite dictionary entries. The stack validates catalogs before
they reach this registry, and reports active health independently.

`src/app/core/router.py` POSTs mapped tool/arguments and extracts only the
downstream JSON `result`. HTTP 200 means success even when the nested tool result
is an error. Calls have explicit timeout and a per-server circuit breaker.
**Calls are not retried**: retry_attempts affects health only. Circuit failures
are counted per failed call; reset uses wall clock, without a single-probe
half-open gate. Domain failures must remain HTTP 200 so they do not open circuits.

`src/app/main.py` provides `/tools`, `/call`, `/servers`, `/servers/refresh`,
`/health`, `/status`, `/ready`, `/metrics`, `/metrics/prometheus`. The selected
revision includes API-key/bearer authentication and an in-memory per-IP limiter.
Readiness returns HTTP 200 even when ready=false and requires only one online
server. Prometheus text is returned as a JSON-encoded string. Open circuit counts
include expired entries until a successful call. W3C context is not forwarded.
The YAML `cache` section has **no result-cache implementation**.

The upstream Dockerfile references missing README.rst, installs before copying
the version source, and healthchecks with curl without installing it. The
pyproject also references the missing README.rst. CI references nonexistent
requirements_dev.txt and its final pytest line is incorrectly indented YAML.
The bundled Compose adds unused Redis and publishes every service broadly.

## Integration decision

Use the original dependency source at an immutable commit without patching it.
Build an operational image around that source with locked runtime dependencies;
do not invoke its broken packaging/Dockerfile. A generated config is mounted
at its existing `src/config.yaml` path. No source is copied into the stack Git
history and no routing/circuit-breaker implementation is duplicated.

Topology: native MCP edge -> MCP One REST -> internal REST/MCP bridge -> native
scientific MCP. Both compatibility adapters live in services/gateway_edge.
Native tool definitions travel losslessly inside the legacy parameters map;
CallToolResult travels inside the legacy result field. The external edge unwraps
it. Scientific arguments and W3C context travel in separate internal invocation
fields, removed before calling the downstream SDK. See ADR 0002.

## Protocol gap

The target is [MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28).
MCP One implements none of its wire requirements: stateless discovery, version
metadata/headers, method/name headers, native error/result semantics or schema
dialect. The stack delegates these to [official Python SDK v2](https://github.com/modelcontextprotocol/python-sdk).
Upstream changes required to remove the adapters are in mcp-one-upgrade-path.md.
