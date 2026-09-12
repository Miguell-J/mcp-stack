# Native MCP One integration

MCP One is now the native gateway at both boundaries. The source of truth for its
immutable commit is config/stack.yaml. Bootstrap verifies its official origin,
clean working tree and exact revision, compiles/imports the native package and
installs its own uv.lock. Docker builds that checkout's upstream Dockerfile;
no copied router, monkeypatch or source rewrite is used.

The manifest renderer maps server id/display_name/namespace, native transport URL,
auth environment references, independent timeout budgets and circuit policy into
MCP One config. Scientific contract metadata remains a stack/adapter concern.
Health URLs in manifests are optional operational fixture/container probes, not
a prerequisite used by the MCP registry. Native discovery is the integration contract.

Tests use real HTTP processes: SDK client -> MCP One -> scientific mock. They
compare direct and routed tool definitions and identity_matrix, contract_error and
artifact results, including schemas, content, structuredContent, isError, all
original metadata, diagnostics/provenance and opaque artifact references. Fault
tests verify timeouts, circuit recovery, process outage, invalid output/schema,
external references and collisions.

Infrastructure errors now use io.github.miguell-j.mcp-one/error. Domain errors
retain io.github.miguell-j.scientific/error. There is no domain-code mapping in
the gateway. See ADR 0007 and the upstream migration guide.

The former default-branch syntax failure and REST limitations are recorded in
[the historical audit](history/legacy-mcp-one-audit.md). They describe the old
revision, not the native implementation selected by this stack.
