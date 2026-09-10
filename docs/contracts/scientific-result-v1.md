# Scientific MCP Contract v1

The external protocol is native MCP. The contract describes scientific content
inside that protocol, not another request/response envelope.

| MCP field | Responsibility |
| --- | --- |
| content | concise human-readable summary; may also include resource links |
| structuredContent | ScientificResult[T] for successful scientific data |
| isError | tool failure semantics; inspect before using data |
| _meta | infrastructure, routing, tracing and stable error descriptors |

ScientificResult[T] contains required `data: T`, optional ScientificContext,
Diagnostics and Provenance. T must be a concrete model/type for each tool;
unparameterized arbitrary data is rejected at the scientific catalog boundary.
The reusable package only imports Pydantic. MCP result construction belongs to
the adapter, not to a scientific library or the generic contract model.

ScientificContext supports assumptions, coordinates, parameters, conventions,
units and domain. Diagnostics contains structured DiagnosticWarning and
DiagnosticCheck lists, optional numerical diagnostics and completeness. Warnings
have code, severity (info/warning/error), message, optional JSON-pointer path and
details. Checks have name, status (passed/failed/not_applicable/not_checked),
value, expected, nonnegative tolerance and details. Completeness is complete,
partial or unknown. Empty optional sections may be omitted.

Provenance names the scientific library and its version, plus optional backend,
backend version, algorithm, precision, deterministic flag and seed. It must
describe the computation actually used. A gateway cannot fabricate provenance
or treat the absence of deterministic=true as proof that caching is safe.

The gateway's `_meta["io.github.miguell-j.mcp-one/gateway"]` contains requestId,
server, tool, durationMs, attempts when observable, cached, traceId and spanId.
Scientific provenance never stores these fields. The SDK alone owns reserved
MCP metadata. W3C trace context is carried using standard OpenTelemetry APIs.

## Schema and examples

Use `schema_for(ScientificResult[ConcreteData])` or the SDK annotation
`Annotated[CallToolResult, ScientificResult[ConcreteData]]`. The latter lets the
adapter preserve concise content while the SDK validates structured output.
The mock tests compare runtime results to the exact tools/list outputSchema.

`make contract-docs` regenerates [the executable contract example](example-v1.md).
Tests compare that document against generation from the actual response model.
`make tools` or `scripts/tool_catalog.py --json` exposes live schemas for automated
tool documentation. No hand-maintained duplicate schemas are needed.

## Versioning policy

Software uses SemVer; the contract major is independently v1. Its four top-level
keys and their meanings are fixed. v1 producers and consumers use strict models.
Compatible fixes may clarify docs, improve validation without rejecting previously
valid values, or populate already-optional fields. New readers must continue to
accept old valid results. Do not add emitted envelope keys, required fields, enum
values or change encodings/meanings silently: strict old readers could fail.
Those changes require a new contract major or an explicitly versioned tool output
contract and migration tests. Context/details maps are the bounded JSON extension
points already defined in v1. Tool-specific T evolution is separately versioned
and subject to the same compatibility tests.
