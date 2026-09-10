# ADR 0002: Native MCP edge with removable legacy compatibility

Status: accepted, 2026-09-10.

Context: empirical POST /mcp to the original hub returns 404. Both its public and
downstream interfaces are custom REST. Its registry drops native schema metadata.

Decision: use the official MCP SDK v2 for an ingress facade and an internal
REST/MCP bridge. Both live in services/gateway_edge and use one runtime image.
All tool calls pass through the unmodified MCP One router. Full native tool
definitions are transported in its existing opaque parameters map, and complete
CallToolResult objects in its existing result field. The bridge removes exactly
one namespace prefix before the hub adds it. Scientific arguments are separate
from the internal invocation carrier holding standard W3C context.

Consequences: two temporary processes are necessary because there are two protocol
boundaries. Neither implements JSON-RPC framing, a second circuit breaker or a
domain router. The public edge uses the low-level **public** SDK Server because
its catalog is dynamic and must retain exact downstream schemas; the mock/template
use high-level MCPServer. Resource federation and multi-round execution are deferred.

Preferred final architecture: MCP One itself exposes native MCP and consumes native
downstreams. Remove both adapters once its transport abstraction and lossless tool
model pass these same integration tests. See docs/mcp-one-upgrade-path.md.
