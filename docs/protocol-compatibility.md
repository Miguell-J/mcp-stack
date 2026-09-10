# Compatibility

| Layer | Pin / target | Meaning |
| --- | --- | --- |
| mcp-stack | 0.1.0 | SemVer software release |
| MCP protocol | 2026-07-28 | Native edge and mock target |
| Official Python SDK | mcp 2.2.0 / mcp-types 2.2.0 | Wire framing, discovery, negotiation, HTTP and native types |
| MCP One | dafd1e1ed681a05f2dc7ea0c0e7ab796036c9689 | Unmodified legacy REST implementation |
| Scientific contract | v1 / package 1.0.0 | Independently versioned scientific result/data representation |
| Codex | Installed CLI with `mcp add --url` | No hard version floor; syntax checked locally |
| Python | >=3.12,<3.15 | Docker 3.12.12; local tests also 3.14.3 |

The SDK implements core stateless requests, server/discover, per-request metadata,
Streamable HTTP, MCP-Protocol-Version, Mcp-Method and Mcp-Name, including mismatch
validation. The stack does not construct protocol responses or version fallbacks.
It uses stateless_http=True to avoid hidden application sessions and supports
SDK-managed older handshake clients where available. Tests use the SDK's legacy
connection mode specifically to check that compatibility.

inputSchema and outputSchema use JSON Schema 2020-12. Pydantic/SDK generate the
schemas and actual runtime output is checked against the advertised definition.
Scientific results use content, structuredContent, isError and namespaced _meta.
The SDK may add reserved protocol metadata, resultType and discovery/cache fields.
Those are native MCP fields, not a custom scientific wire protocol.

Discovery hints default to ttlMs=0 and cacheScope=private. There is no result cache.
Legacy clients can ignore cache hints; modern clients must honor protocol freshness
and authorization scope. The static server/discover response belongs to the SDK.

Tools-only aggregation is the MVP capability. Resource references are preserved,
but resource federation, prompts, subscriptions, tasks, input-required workflows,
sampling and elicitation are not advertised by the edge. `resultType` must be complete.

Sources: [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28),
[transport model](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports),
[official SDK](https://github.com/modelcontextprotocol/python-sdk),
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
