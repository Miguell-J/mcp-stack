# ADR 0007: MCP One owns the native edge and downstream protocol

Status: accepted, 2026-09-10. Supersedes ADRs 0002, 0004's trace bridge, 0005's
packaging workaround and 0006's placement of the public entrance.

MCP One has been rewritten upstream as a domain-independent native MCP gateway.
The temporary adapters are no longer necessary. Remove services/gateway_edge,
legacy REST mapping/rendering and the two Compose services. Publish MCP One's /mcp
directly on the existing loopback port. Move the entrance network to MCP One;
scientific backends remain internal. Build the official upstream Dockerfile from
a clean immutable checkout using its lock, not a copied-source packaging workaround.

The stack retains manifests, scientific contracts, fixtures/templates and real
SDK tests. It renders only operational MCP One configuration. Scientific errors
remain in the scientific namespace; infrastructure errors belong to MCP One.
Trace context passes through native MCP, while all downstream result/schema fields
remain unchanged. No science import is introduced into the gateway.

Consequences: stack 0.2 configuration/health/metrics migration is explicit. The
upstream pin must be available from the official origin and bootstrap must refuse
dirty/ref-mismatched checkouts. Acceptance requires protocol E2E, direct-vs-routed
scientific envelope comparisons, Docker E2E and no adapters in the normal path.
Resources federation and public OAuth remain deferred. Old audits are historical.
