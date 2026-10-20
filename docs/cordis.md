# Cordis consumer integration

Cordis is the provider-neutral orchestration layer in the sibling checkout
`cordis`. Stack composes the deployment and scientific adapters;
the pinned MCP One owns native transport, registry, routing, circuits and telemetry.
Cordis does not duplicate these services or import scientific domain implementations.

Start Stack using its existing locked bootstrap/render/health workflow. Enroll the
loopback gateway in a reviewed Cordis capability manifest, then run:

```bash
cordis --manifest project.json mcp doctor
cordis --manifest project.json mcp tools gateway
cordis --manifest project.json mcp tools gateway --schema demo.echo
cordis --manifest project.json mcp call gateway demo.echo arguments.json
```

Example operator input (this does not modify Stack's generated configuration):

```json
{
  "version": 1,
  "servers": {
    "gateway": {
      "url": "http://127.0.0.1:8765/mcp",
      "enabled": true,
      "allow_tools": ["demo.echo"],
      "read_only_tools": ["demo.echo"],
      "timeout_seconds": 10
    }
  }
}
```

Use the actual installed catalog, not this example, to establish grants. Tokens are
environment-name references (`bearer_env`); never place values in manifests or docs.
Cordis returns native results and separate operation evidence. Discovery does not
grant execution and reference/tool annotations are not authorization.

Do not enroll the Cordis facade as a downstream of the same gateway that it calls:
that would introduce a routing cycle. Clients connect to Cordis separately. Additional
catalog entries are candidates, not installed Stack services. Add approved servers
through the existing Stack manifests and pinned MCP One capabilities. No gateway,
legacy bridge, generated file or dependency pin is changed by this integration.

Cordis validates its SDK client/facade with real HTTP/stdio fixtures and an opt-in
test against the unmodified sibling MCP One. This does not establish that Compose
or all catalog servers have been deployed. See Cordis's validation record for actual
executed checks. Container/production adoption remains the operator's decision.
