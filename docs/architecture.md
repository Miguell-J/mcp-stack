# Architecture

The dependency direction is library -> imported by thin adapter -> called by
infrastructure. A library can be used without any MCP components installed.
The reusable scientific contract package depends only on Pydantic, not MCP.

| Component | Owns | Does not own |
| --- | --- | --- |
| mcp-stack | manifests, rendering, contracts, operation, tests | domain algorithms |
| MCP One | registry, REST routing, health retries, circuit breaker, rate limiter | scientific meaning |
| Native edge | native MCP facade, validation, error mapping, metadata | downstream execution or circuit breaking |
| Legacy bridge | REST to official MCP client, lossless definitions/results | scientific tools or a second router |
| Scientific adapter | library calls, typed results, tool-specific schemas | gateway policy |
| Domain library | mathematics, algorithms, scientific truth | protocol, Docker, Codex |

## Why four runtime processes

The legacy hub cannot speak MCP on either side. An ingress adapter alone would
leave MCP One sending REST requests to a native MCP server. The bridge exposes
the three endpoints its YAML mapping supports and translates them through the
official SDK client. Both adapters share a code package and image; they have
different network exposure and lifecycle. ADR 0002 records removal conditions.

## Discovery

1. Client sends native tools/list. SDK handles server/discover and protocol fields.
2. Edge asks MCP One to refresh and reads its catalog and health statuses.
3. MCP One calls bridge health/tools, using generated manifest paths.
4. Bridge discovers native downstream tools with bounded pagination, validates
   schemas and rejects collisions before the legacy registry can overwrite them.
5. Each full native Tool definition is stored under `parameters.x-mcp-stack-native-tool`.
   This exploits the existing opaque mapping without changing MCP One.
6. Edge restores the native definition, applies exactly one namespace and omits
   unhealthy servers from discovery. All published schemas come from the downstream.

MCP One retains its historical catalog internally during outages. Previously
known tool calls still return an infrastructure error; discovery advertises only
healthy sources. Discovery TTL defaults to zero/private to avoid stale scientific
contracts while legacy refresh semantics remain coarse.

## Calls

The edge validates arguments and wraps them, the W3C carrier and a request ID in
an internal invocation object. MCP One selects the server and applies its circuit
breaker, then forwards the invocation to the bridge. The bridge unwraps arguments,
calls the native server and validates the response. It sends `{"result": CallToolResult}`
to the hub, which forwards that opaque result. The edge removes the REST envelope
and adds gateway metadata. No math is interpreted or transformed in this path.

The edge's gateway object has no scientific state. Each downstream operation
opens an SDK client context and closes it; no session affinity, database or shared
cache is required. MCP One's registry, rate buckets and circuit counters are
ephemeral local process state. Run a single hub replica in this MVP; restarts
reset those controls. Future durable experiments need explicit handles.

## Scope

The public facade aggregates tools. Artifact/resource references survive results;
the mock's resource is independently readable through its MCP interface, but
generic resources/list/read federation is not advertised at the gateway yet.
No tasks, elicitation, sampling, mutable tools, jobs or result caching are enabled.
The compatibility bridge rejects non-complete multi-round results explicitly.
