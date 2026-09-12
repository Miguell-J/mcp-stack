# Protocol compatibility

| Layer | Target |
| --- | --- |
| mcp-stack | 0.2.0 |
| MCP | 2026-07-28 |
| Official Python SDK/types | 2.2.0 |
| MCP One | native 1.0 candidate; immutable commit in config/stack.yaml |
| Scientific contract | v1, package 1.0.0 |
| Python | >=3.12,<3.15; containers 3.12.12, local host 3.14.3 |
| Codex | Streamable HTTP --url; use current CLI syntax |

The official SDK owns stateless server/discover, tools/list and tools/call,
per-request metadata, JSON-RPC/framing, MCP-Protocol-Version, Mcp-Method, Mcp-Name
and W3C trace propagation. Native calls carry no semantic session history.
SDK-provided legacy handshake compatibility remains covered by real-client tests.

JSON Schema 2020-12 input/output definitions pass through unchanged. Native
content, structuredContent, isError and _meta remain intact. ScientificResult,
diagnostics, provenance and artifact references are opaque to the gateway.
Successful results are validated against outputSchema; domain error results do
not pretend to conform to the successful data shape.

Gateway discovery is private TTL zero. Its operational catalog refresh/stale
policy is explicitly separate from response freshness. No tool result cache
exists. The capability scope is tools federation only: resources, subscriptions,
tasks, elicitation/sampling and multi-round continuations are not advertised.

Sources: [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28),
[official SDK](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0).
