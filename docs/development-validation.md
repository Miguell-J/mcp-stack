# Scientific development validation

Existing checks already cover concrete ScientificResult[T], input/output schemas,
artifact hashes, direct-versus-routed content and metadata, protocol failures and
recovery. Additional adversarial tests mutate actual returned payloads against the
actual advertised outputSchema and validate concrete models. Optional context,
diagnostics and provenance remain optional in v1. No schema or pin is weakened.

JSON Schema handles structural constraints. Pydantic model validators also enforce
cross-field dimensions such as matrix shape versus component lengths; standard
JSON Schema cannot express that relationship. Adapters must construct validated
models before serialization. Passing either layer does not establish scientific
correctness, convergence, interpretation or approval of a hypothesis.

```bash
make test-contract test-template
make test-integration test-e2e
make health tools
STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e
```

Tests use the clean upstream revision in `.deps/mcp-one`. Changes in the companion
MCP One development checkout are not silently injected into the pinned stack.
Repeated scientific domain errors must preserve their stable scientific metadata
and leave the infrastructure circuit closed. Follow the existing direct-versus-
routed test to compare provenance, diagnostics, structured data and trace metadata.

For Inspector, the companion MCP One owns the pinned development package and
[procedure](https://github.com/Miguell-J/mcp-one/blob/master/docs/inspector.md).
With that checkout present, install using `npm ci --ignore-scripts --prefix
/workspace/mcp-one/tooling`. Against a running stack, run its CLI:

```bash
MCP_INSPECTOR_SECRET_STORE=memory \
MCP_STORAGE_DIR="$PWD/.generated/inspector" \
MCP_INSPECTOR_OAUTH_STATE_PATH="$PWD/.generated/inspector/oauth.json" \
  /workspace/mcp-one/tooling/node_modules/.bin/mcp-inspector --cli \
  --transport http --server-url http://127.0.0.1:8765/mcp \
  --protocol-era modern --connect-timeout 5000 \
  --method tools/list --strict --format json
```

`demo.echo` is a harmless fixture for real calls; do not use a new mutating tool as
an automatic smoke check. If the companion checkout is absent, keep the Python
checks working and consult the official Inspector procedure; this repository does
not depend on a sibling directory to build or run its production stack.

Project-local opt-in skills: `scientific-contracts` and `stack-integration`.
Generated cloud Compose overrides from onboarding remain local; use the saved
startup instructions in that environment. Inspector adds no service, gateway,
protocol bridge, registry or production dependency here.
