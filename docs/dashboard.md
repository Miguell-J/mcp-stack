# Local monitoring dashboard

Run `make bootstrap` and `make up`, then open **http://127.0.0.1:8766**.
The endpoint for Codex remains **http://127.0.0.1:8765/mcp**.

The panel shows gateway readiness, enabled/disabled server inventory, circuits,
catalog freshness, native tools and aggregate operational metrics. Searching the
catalog does not execute a tool. Pause affects only browser updates; the observer
continues collecting. Update reads the latest observation, not a forced gateway
registry refresh. Each viewer shares the same observation stream.

Use the theme button in the top bar to switch between light and dark modes. The
initial theme follows the operating system; an explicit choice persists in browser
local storage. No account, network preference storage or tracking is involved.

Each tool has **Ver contrato de resposta**, opening a keyboard-accessible modal
with its complete `outputSchema`. The Entrada tab shows the original `inputSchema`.
Both preserve nested definitions and references; Copy JSON copies the entire schema.
Escape or Close dismisses the dialog and returns focus to the tool. Missing response
schemas and stale observations are explicitly identified. These are advertised
request/response contracts, not captured payloads or a history of executed requests.
Schemas are fetched from the observer's cached catalog only when a modal is opened,
so routine overview polling does not repeatedly transfer large schema definitions.

## Configuration

Edit `config/stack.yaml`, then run `make up`:

```yaml
dashboard:
  enabled: true
  bind: 127.0.0.1   # or ::1; no wildcard/public bind
  port: 8766       # must differ from the gateway listener
  poll_seconds: 5  # 2–60; interval after each observation completes
  timeout_seconds: 3  # 0.1–15; per observation operation
```

The generated JSON Schema includes these fields. `enabled: false` omits the service;
when removing it from an already running deployment, use `make down` then `make up`
to remove the old container. The UI uses the mounted read-only manifests and talks
to the fixed internal `http://mcp-one:8000`. Changed manifests require restarting
the dashboard to reload its inventory; `make restart` guarantees this. The UI's
inventory and the gateway's enabled server IDs must agree; disagreement is reported
as an invalid observation, not a healthy but incomplete inventory.

`gateway.admin_token_env` authorizes backend reads of status/metrics, while
`gateway.token_env` authorizes native discovery. Both remain environment references.
Configured but missing credentials prevent dashboard startup. Credentials never
reach the browser; downstream credential references are not forwarded to the UI service.

## What the numbers mean

| Signal | Meaning |
| --- | --- |
| Gateway pronto | MCP One says it can route useful permitted calls |
| Degradado | Useful routing remains, but an enabled server/catalog is not fully healthy |
| Servidores aptos | Enabled servers for which MCP One reports readyToRoute |
| Desabilitado | Present in manifests, not enrolled in the gateway; not an outage |
| Sem conexão/observação | An observation failed; retained values are historical |
| Tools | Last observed aggregate catalog size, with registry generation |
| Chamadas | Cumulative gateway tool-call counter, including failures/unknown tools |
| Calls/min | Change in call counter divided by real elapsed time between observations |
| Latência média | Histogram sum/count across calls in the current gateway process |
| Latency graph | Histogram sum/count deltas for each observed interval |
| p95 · limite superior | Upper bucket boundary containing at least 95% of observed latencies |
| Chamadas sem sucesso | Failed/cancelled/rejected calls divided by calls within the interval |
| Erros de domínio | Downstream isError outcomes, separate from infrastructure failures |
| Circuitos abertos | Cumulative circuit-open events, not currently open circuit count |
| Registry | Refresh attempts and discovery-cache hit/miss counters |

Metrics are not reset by opening the browser. Histories contain up to 120 real
observations (approximately ten minutes at default interval), shared across viewers.
A missing observation produces a gap, not zero. A decreasing counter after gateway
restart starts a new baseline. No calls means no interval latency sample. The
dashboard reports actual histogram means and explicitly labelled p95 bucket upper
bounds, not interpolated/exact quantiles. If p95 falls in the infinite bucket, the
card says Fora da escala; no finite latency is invented. Cumulative indicators cover
the gateway process; charts use interval deltas. Per-server calls, mean latency and
unsuccessful-call percentage are shown in the inventory. An initial zero-call
graph is normal before clients use the tools. Gateway counters include observation
discovery traffic in catalog-cache metrics, but polling does not call any tools.

Infrastructure failures count failed attempts, which can exceed failed requests
when safe retries occur. They are never used as the numerator of the call-error
percentage. That percentage comes from final `tool_calls` outcomes, including
domain errors, cancellation and policy/routing failures. Empty intervals have no
latency/error-rate sample; they do not imply zero latency or 100% success.

Tool summaries come from SDK `tools/list` every thirty seconds, with bounded page
and tool counts; the trusted pinned gateway bounds/validates schemas and responses.
The UI presents input/output schemas without rewriting them or substituting for
the MCP catalog. Descriptions and schema JSON are rendered as plain text.
Discovery failure retains the last catalog and marks it unavailable. No data is
saved to disk; dashboard restart clears its observation history.

## Security and lifecycle

The local dashboard is read-only and has no login. It exposes operational metadata
to users able to connect to localhost; disable it if other local users must not see
that data. Browser Host/Origin/fetch-site checks and CSP limit cross-site access and
script injection. It serves only bundled assets and never accepts viewer-supplied
network destinations. Status/metrics responses are capped at 4 MiB, redirects and
compression are rejected, and operations have deadlines. Authentication errors use
stable error codes; raw errors, tokens and response bodies are not displayed.

`/health` reports the observer task's liveness, independently of gateway readiness.
`/api/overview` returns the current read-only observation. `/api/contracts/{name}`
returns the cached schema for a known tool, with observation time and availability.
Unknown names return 404 and never initiate network calls. One background task owns
the polling lifecycle; shutdown cancels it and closes both HTTP pools. The container
runs non-root with a read-only filesystem, dropped capabilities and no Docker socket.

The panel does **not** inspect host CPU/RAM, container resource use, logs, stored
traces, payloads, artifacts or scientific semantics. Use Compose logs and the
optional OTel collector for their respective signals. External scientific libraries
still need native MCP adapters with concrete schemas and manifest registration;
installing a library alone does not expose its functions as MCP tools.

## Validation

Local validation on 2026-09-12: 83 Python tests passed (host Python 3.14), plus four
Chromium browser tests against the running Docker stack (runtime Python 3.12).
The general suite skips those four browser tests unless its explicit endpoint is
set; they were run separately with desktop/mobile screenshots. Native Docker E2E
passed all six scenarios, and the scientific adapter template test passed. Ruff,
format checks and strict mypy passed (28 source files). The runtime Docker build
and health checks passed for gateway, scientific fixture and dashboard.

Browser tests cover theme persistence, contract modal input/output schema equality,
keyboard/focus behavior, copying complete JSON, missing schemas, injected text,
search/pause/refresh, actual latency/error chart samples and stale recovery. Python
integration tests compare modal schemas against the real downstream SDK catalog
and exercise authenticated observations, a real gateway shutdown and recovery.
Metrics tests distinguish retries from failed requests and cover histogram limits,
counter resets, per-server aggregation and gaps. No payload capture is used.

The first remote browser run exposed an assertion timeout of five seconds during
cold-start catalog refresh. Locator assertions now allow the documented discovery
interval plus request/poll time; this does not change production refresh semantics.
Cold-start CI also exposed that Compose liveness can precede gateway catalog
readiness. `make up` now waits up to 60 seconds for useful routing after container
health, and fails visibly if it is unavailable. The browser fixture waits for a
metric baseline before generating two native test calls, so graph checks do not
depend on image or browser installation speed.

```bash
make lint test test-integration
make up
make health tools
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
.venv/bin/uv sync --locked --group browser
.venv/bin/playwright install --with-deps chromium
DASHBOARD_ENDPOINT=http://127.0.0.1:8766 .venv/bin/python -m pytest tests/browser -q
```

With an installed Chromium, set `BROWSER_EXECUTABLE_PATH=/usr/bin/chromium` instead
of downloading a browser. `DASHBOARD_SCREENSHOT_DIR` optionally retains desktop and
mobile screenshots. CI validates the screen against the running Compose stack.
