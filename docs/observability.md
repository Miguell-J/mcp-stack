# Observability

MCP One owns structured gateway logs and an OTel route span; the official SDK emits
native client/server spans. W3C trace context now crosses native HTTP/MCP directly.
No hidden trace carrier is embedded in scientific tool arguments. Tests correlate
mock and gateway trace IDs and compare all original result metadata.

Gateway metadata includes UUID requestId, server/tool, durationMs, actual attempts,
cached=false, route generation, traceId and spanId under
io.github.miguell-j.mcp-one/gateway. Existing keys are retained; nested gateways
append a numbered hop key. Scientific provenance is unchanged.

GET /metrics on MCP One is Prometheus text. Counters/histograms cover tool calls,
latency, infrastructure/domain errors, timeouts, circuit openings, registry refresh,
health probes and catalog size. Labels are configured servers and stable outcomes,
never payloads or arbitrary users. GET /status supplies administrative diagnostics.
Health is lifecycle liveness; readiness requires useful permitted routes while
allowing partial degradation. No network checks run on Prometheus scrapes.

Set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT to the optional collector's HTTP traces
endpoint to export; otherwise no trace export occurs. The development collector
is not durable telemetry storage. Use docker compose --profile core logs --tail=100
mcp-one mock-scientific-mcp. Do not enable SDK/HTTP payload logs on secret traffic.
