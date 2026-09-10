# ADR 0001: Stack boundaries

Status: accepted, 2026-09-10.

Context: independent scientific libraries need a central operational integration
without taking a dependency on gateways, MCP or a particular assistant.

Decision: mcp-stack owns composition, manifests, reusable result types and tests.
MCP One owns control-plane routing and resiliency. Thin MCP adapters own tool
schemas and result conversion. Domain libraries own algorithms. Configuration is
validated with Pydantic and rendered once for Compose and the legacy hub.

Consequences: adding a backend normally changes one manifest and an independent
adapter/container. No gateway mathematics or domain-specific switch statements.
The shared contracts package has no MCP dependency. Deployment is local-first
Docker Compose, with no unnecessary database, Redis or Kubernetes dependency.
