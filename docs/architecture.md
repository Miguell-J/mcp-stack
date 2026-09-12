# Architecture

```mermaid
flowchart TD
    C[Codex / MCP client] --> H[MCP One /mcp]
    H --> A[Native scientific MCP A]
    H --> B[Native scientific MCP B]
    A --> L[Independent domain library]
    M[Stack manifests] --> G[Generated native config + Compose]
    G --> H
    O[Local operator :8766] --> D[Read-only stack dashboard]
    D -. status / metrics / native tools/list .-> H
```

| Component | Responsibility |
| --- | --- |
| mcp-stack | composition, manifests, contract package, operation, integration tests |
| Local dashboard | bounded read-only gateway observations, inventory and presentation |
| MCP One | native MCP edge/client, registry, routing, policy, retry/circuit safety, telemetry |
| Scientific MCP adapter | library invocation, typed schemas, ScientificResult and domain errors |
| Domain library | scientific meaning and algorithms, independent of MCP |

The default core deployment has three services: MCP One, the scientific mock and
the local monitoring dashboard. The dashboard is outside the MCP execution path
and can be disabled with `dashboard.enabled: false`.
Additional backends are added by manifest. There are no REST tool adapters or
legacy result envelopes. MCP One builds its catalog using native discovery and
returns CallToolResult unchanged except for additive gateway metadata.

MCP One maintains atomic operational snapshots, pooled HTTP clients and circuits;
none is semantic user-session state. The stack does not duplicate these mechanisms.
Native domains carry data/context/diagnostics/provenance; gateway tracing stays
in its own _meta namespace. The scientific contract package depends only on
Pydantic. MCP One does not import that package or interpret mathematical data.

The hub and dashboard join entrance and internal scientific networks and publish
separate loopback ports (8765 and 8766). Backends remain on the internal network.
ADR 0008 defines the optional read-only monitoring service. ADR 0007 supersedes the
old four-process compatibility architecture. Historical audits remain explicitly
archived under docs/history, not operational instructions.

The gateway advertises tools only. Artifact/resource references survive, while
resource federation, sampling, subscriptions, tasks and multi-round workflows
are outside the current scope. No result caching is enabled.
