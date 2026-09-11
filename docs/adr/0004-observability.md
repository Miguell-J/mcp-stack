# ADR 0004: OTel and explicit cache semantics

Status: superseded by ADR 0007; originally accepted, 2026-09-10.

Decision: use SDK OTel spans and W3C inject/extract. Add request/route/duration and
typed error metadata to JSON logs without inputs, output bodies or secrets. Carry
the standard W3C carrier opaquely through legacy MCP One, then restore it at the
bridge. Do not pretend the uninstrumented legacy hub emits a span.

Discovery cache hints default to private TTL zero while the legacy registry's
refresh semantics are imperfect. The operator can raise the advertised TTL with
an explicit stale-catalog tradeoff. Result caching is entirely disabled in v1;
future caching needs explicit per-tool determinism, provenance and mutation policy.

Consequences: useful correlated traces without a collector; optional OTLP export
to a small internal Collector, no Grafana stack. Attempt counts reflect the
original router's actual one-shot behavior, and unknown counts are omitted.
