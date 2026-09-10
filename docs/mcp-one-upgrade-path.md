# MCP One upgrade path

The final architecture should be Codex -> MCP One native MCP -> native scientific
MCPs. This stack can remove both temporary compatibility adapters once upstream
owns the following small, domain-independent integration surfaces.

1. Repair the default-branch syntax/merge damage, metadata packaging, original
   tests, Docker build and CI YAML. Preserve current REST endpoints for existing users.
2. Add official SDK v2 as an optional/explicit runtime dependency and mount its
   stateless native /mcp ASGI application beside REST. Expose tools/list and tools/call
   through the existing registry/router service interfaces, not a second router.
3. Extend tool records to retain native Tool inputSchema/outputSchema, annotations,
   metadata and original name. Validate catalog collisions and schemas atomically
   before replacing the last good registry. Make namespaces explicit and deterministic.
4. Add a transport abstraction behind registry/router with the existing REST client
   and an official native MCP client implementation. Do not make the router know
   scientific contracts or mathematical objects; route full native CallToolResult.
5. Keep native domain isError distinct from infrastructure failure for breaker and
   metrics. Publish stable typed infrastructure failures, timeout categories and
   real attempt count. Never infer an error category from free-form exception text.
6. Add W3C/OTel propagation at the HTTP/MCP boundary and downstream client. Correct
   readiness HTTP status, metrics MIME type and expired-circuit accounting. Clarify
   that health retries are not tool retries. Add a proper single-probe half-open
   transition only if needed by concurrency tests; do not retrofit it into this edge.

Acceptance upstream: this repo's native client and fault tests pass against MCP
One directly, lossless schemas/results/metadata survive, domain errors do not open
circuits, invalid catalogs are rejected and a stopped/restarted downstream recovers.
Run older-client compatibility tests through the SDK too.

Migration in this repo: pin the upgraded image/commit, point the public Compose
binding at MCP One /mcp, render native transport configuration, run the same tests,
then delete services/gateway_edge and its two services in one ADR-backed change.
Keep contracts, manifests, mock, template, operational scripts and docs. No scientific
library code needs to change. The image option in stack.yaml allows replacing the
source build with a versioned image before or after that migration.
