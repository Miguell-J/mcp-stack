# ADR 0008: Local read-only monitoring dashboard

Status: accepted. Date: 2026-09-12.

## Context

The native stack has operational signals but needs a browser view for the local
operator. The dashboard must not become another edge, execute tools, duplicate
gateway health/routing policy, or require privileged access to Docker.

## Decision

Add an optional `dashboard` service to the core profile, enabled by default on
loopback port 8766. It uses the existing stack runtime image, Starlette and static
HTML/CSS/JavaScript. A single lifecycle-owned observer pools HTTP connections,
reads MCP One `/status` and `/metrics`, and uses the official SDK for native
`tools/list`. All browser requests read the cached snapshot. No arbitrary proxy,
remote config mutation, tool execution or downstream health polling is provided.

Gateway readiness, circuit state and catalog freshness remain authoritative at
MCP One. Observations are explicitly marked unavailable on failure; last valid
values remain identifiable as historical. Disabled manifests stay distinct from
offline servers. The UI is not required for MCP execution or readiness.

## Consequences

The normal execution path remains client → MCP One → native server. An additional
optional loopback port exposes operational metadata to trusted local users. The
dashboard receives only referenced gateway admin/MCP credentials; never downstream
tokens. Host/Origin checks, CSP, text-only rendering and no Docker socket constrain
the surface. Local processes remain trusted; public multi-user deployment is out
of scope. History is in memory, bounded to 120 samples, and lost on restart.

Performance charts use deltas of gateway counters and histogram sums/counts.
Percentiles are explicitly upper bucket bounds; failed attempts are separate from
failed calls. Contracts are cached as published and fetched by tool name when a
schema modal opens. No result capture or domain-specific schema interpretation is
introduced. Light/dark preferences stay in local browser storage.

No frontend package manager or CDN is needed. Playwright is an optional test-only
dependency group; it is absent from runtime images. Browser tests cover real
Compose signals, responsive layout, search, pause, stale presentation and injection.
