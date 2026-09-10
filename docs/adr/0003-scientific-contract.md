# ADR 0003: Scientific contract independent of the wire

Status: accepted, 2026-09-10.

Decision: version a Pydantic ScientificResult[T] contract independently as v1.
Require concrete per-tool data and outputSchema. Keep human content short, result
data structured, scientific diagnostics/provenance explicit, and infrastructure
metadata outside the scientific result. Domain failures use native isError with
a stable namespaced error descriptor rather than a fake success envelope.

Use JSON Schema 2020-12 generated from models and verified against actual SDK
discovery/results. Keep types small and bounded; large data uses explicit URIs.
No mathematical evaluation belongs in this package. Strict readers make additive
emitted fields potentially breaking; preserve the v1 shape and document upgrades.

Consequences: scientific libraries can adopt the representations without importing
the MCP SDK. Tool-specific outputs remain useful to machines and cannot silently
degrade into unconstrained dictionaries. Gateways preserve, not reinterpret, science.
