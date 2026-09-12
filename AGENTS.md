# Working on mcp-stack

## Responsibility boundaries

- This repository composes/configures/operates infrastructure. Domain libraries
  remain independent. CRR, GeoMech and Variational are out of scope unless the
  user explicitly names a separate domain task.
- Domain logic must never depend on MCP infrastructure. Adapters import libraries;
  libraries do not import adapters, gateway code, MCP or stack configuration.
- MCP One owns registry, routing and circuit breaking. Its official, immutable
  dependency checkout is under `.deps/mcp-one`. Never copy or rewrite its code in
  this repo, monkeypatch its router, or silently change its pin.
- MCP One is the native edge and downstream MCP client. Do not recreate gateway-edge
  or legacy-bridge in the normal path. Use public SDK interfaces in adapters/tests.
  Never implement framing, version negotiation, discovery or handshakes yourself.
- Add servers by manifest/configuration, not tool-specific routing branches.
- Meaningful architectural changes require an ADR and updated operational docs.

## Contracts

- External envelope is native MCP CallToolResult: content, structuredContent,
  isError and _meta. No required success/result/error wrapper on the native edge.
- ScientificResult[T] has required data, optional context/diagnostics/provenance.
  Every scientific tool has a concrete T, inputSchema, outputSchema and tests.
- Generate schemas from models/SDK; validate runtime data against advertised
  outputSchema. Never weaken types or alter scientific results to make tests pass.
- Contract v1 has its own version. No silent breaking changes. New incompatible
  fields, meanings, encodings or enum values require a new contract major/ADR.
- Protocol, infrastructure and domain errors are distinct. Domain errors use
  isError and stable error metadata. They must not open infrastructure circuits.
- Warnings are structured, provenance is scientific, gateway tracing belongs
  in namespaced _meta. Never use protocol-reserved namespaces for private fields.
- Large objects use explicit artifact/resource/job handles, not hidden sessions.
- Tool annotations are hints. They do not authorize access or justify caching.

## Sources of truth and reproducibility

- Edit config/stack.yaml and config/servers.d/*.yaml. Run make render.
- Never manually edit .generated or config/schemas/stack.schema.json. Their
  GENERATED FILE notices and drift tests must remain correct.
- Keep uv.lock up to date and run uv sync --locked in CI/builds. No latest image
  tags, floating MCP One branches, bootstrap auto-pulls or hidden source patches.
- Preserve dirty worktrees and dependency changes. Bootstrap must refuse a dirty
  checkout or unexpected ref, unless the user explicitly requests a clean switch.
- Verify an upstream revision by compilation/import and integration before pinning.

## Verification

```bash
make bootstrap
make render
make lint
make test
make test-contract
make test-template
make test-integration
make test-e2e
docker compose --profile core config --quiet
make up
make health
make tools
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
```

Integration tests launch real local HTTP processes and the unmodified MCP One;
they need permission to bind loopback sockets. Containers use Python 3.12, while
CI also checks 3.14. Do not claim Compose, CI or Codex checks that were not run.
Keep upstream test failures separate from stack results. Tests may inject faults
only in their own processes, and must restore/stop everything in finally blocks.

## Security and operations

- Bind the public endpoint to loopback. Downstreams stay on the internal
  Docker network. No privileged containers, root runtime, socket mounts or secrets
  in Git, logs, generated config, test artifacts or command arguments.
- Secrets are environment references; `.env` is ignored. Never print tokens.
- Bound requests, responses, catalogs, schemas and operation time. Reject external
  schema references; never enable arbitrary schema fetching or redirect following.
- Keep W3C context and standard OTel instrumentation; log names, status, durations
  and trace IDs, never scientific arguments or full returned data by default.
- Result caching remains disabled until explicit per-tool deterministic safety is
  designed and tested. Discovery cache hints follow MCP's private TTL semantics.
- Update README/adding-a-server/compatibility documentation when integrations change.
- Do not modify ~/.codex/config.toml automatically. The generator prints only.
