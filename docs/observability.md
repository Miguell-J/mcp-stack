# Observability

Each edge call emits a JSON `gateway_call` event with requestId, server, tool,
durationMs, attempts when known, cached=false, isError, traceId and spanId.
Each bridge call emits `downstream_call`. Rejections log only error type and
server, not raw exception strings containing arguments, URLs or tokens.

The official SDK emits MCP server/client OTel spans. A standard TracerProvider
is configured even without an exporter, so trace identifiers remain useful in
logs. If the OTLP traces endpoint environment variable is present, a batch HTTP
exporter sends spans. Its absence means no telemetry leaves the stack.

W3C traceparent/tracestate are propagated using OpenTelemetry inject/extract.
MCP One cannot forward trace headers. The edge carries that standard W3C carrier
inside a separate internal invocation field, the hub passes it opaquely, and
the bridge restores the parent before the SDK downstream call. No private trace
format is defined. MCP metadata on the actual native hops is managed by the SDK.
Tests compare the mock and edge trace IDs and inspect actual routed-call counters.

There is intentionally no fabricated MCP One span: it is not instrumented. The
edge duration covers its HTTP request, and the bridge/downstream spans share the
trace across it. Upstream OTel instrumentation is part of the upgrade path.

Attempts count one bridge invocation, or zero for validation/circuit/offline
short-circuits. MCP One does not retry tool calls; health retry count is a distinct
configuration. Attempts are omitted when the edge cannot know if delivery occurred.
Result caching is disabled, so cached=false is factual, not inferred from annotations.

MCP One's private /metrics exposes counters and circuit bookkeeping. Its
/metrics/prometheus response is JSON-encoded text and not directly scrapeable;
do not claim it is a working Prometheus exporter. No extra metrics shim is added.
Health/ready on the edge actively check all enabled downstreams via the bridge,
including valid MCP discovery, and use HTTP 503 for degraded readiness.

Use `docker compose --profile core logs --tail=100 gateway-edge legacy-bridge mcp-one`
and the optional collector profile documented in quickstart. Do not enable debug
payload logging on scientific or authenticated traffic.
