# Adding a scientific server

1. Implement an independent adapter using the template. Keep the real library in
   its own repository and install it as a dependency. Use official MCP SDK tools,
   bounded inputs, concrete ScientificResult[T] and read-only annotations where true.
2. Build/publish an immutable or versioned container image. Run its contract tests.
   Its SDK transport must permit its internal Docker hostname in allowed_hosts.
3. Add a unique manifest in config/servers.d, or edit the existing disabled example.
   Do not leave a second copy with the same ID or namespace. Set enabled=true.
4. For a managed container add `container.image`, `container.command`, `container.port`
   and `container.profile: core` to the manifest. The renderer creates the service;
   no second hand-maintained Compose entry is necessary. For an already-managed
   external service omit container and explicitly arrange network access.
5. Run make validate, make render, make up, make health and make tools. Add a focused
   real-client test and update compatibility/server documentation.

Example fields to add to the future geometry manifest after publishing an image:

```yaml
container:
  image: ghcr.io/miguell-j/crr-mcp:0.1.0
  command: [uvicorn, crr_mcp.adapter:create_app, --factory, --host, 0.0.0.0, --port, '8080']
  port: 8080
  profile: core
```

This image name is a future example, not an implemented CRR MCP. The existing CRR
repository is intentionally untouched. No routing-code edits are required.

For tokens set `transport.token_env: CRR_MCP_TOKEN`; provide the actual secret in
the process environment/.env. The renderer only emits an environment reference.
The health endpoint uses the same credential in this MVP. Do not put tokens in URLs.

The bridge accepts native names `christoffel` or `geometry.christoffel`; both become
`geometry.christoffel`. They cannot both appear in one catalog. It requires outputSchema
with required data and rejects external references and oversized schemas/catalogs.
Schemas and annotations come from discovery, never duplicate YAML tool definitions.

Large results must use ArtifactReference. Add a real resource/artifact retrieval
policy before relying on downloads through the aggregated gateway, which currently
advertises tools only. Native downstream resources are independently available.
