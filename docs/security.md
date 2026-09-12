# Security

The default deployment serves one trusted local operator. MCP One and the optional
dashboard publish separate ports on 127.0.0.1 and join the entrance network.
Scientific containers stay on an internal
network with no published ports. Containers run uid/gid 10001, drop all capabilities,
use no-new-privileges/read-only source and bounded tmpfs, and mount no Docker socket.

MCP One's SDK Host/Origin validation protects the native and administrative edge.
Optional gateway.token_env and gateway.admin_token_env select separate environment
references for local bearer authentication. Downstream transport.token_env is
forwarded only to that configured server. Missing configured credentials fail
closed; generated YAML contains references, not values. No token belongs in a URL.
The fixture is internal; its optional /health URL is for operations, not registry
protocol discovery. No arbitrary client URL is accepted for enrollment or routing.

Public Internet deployment requires HTTPS, proper MCP OAuth resource-server
integration and per-client policy, outside this local composition. Local bearer
security is not advertised as OAuth. The upstream gateway enforces request/response,
schema/catalog and concurrency bounds, rejects redirects and external schema refs,
and does not log bodies/tokens. Only enroll trusted schemas; CPU-hostile regex or
recursive schema isolation requires a separate execution boundary.

Scientific contracts keep their own finite-number/inline-size checks in adapters.
MCP One never imports those models. Artifact references are opaque; they do not
permit the gateway to fetch arbitrary locations. Result caching is absent.
Use namespaced infrastructure errors without fabricating scientific diagnostics.

The [dashboard](dashboard.md) is a local read-only observer, without a login flow.
Any local user able to connect can see inventory, tool names/descriptions/schemas and aggregate
metrics. Keep it disabled on shared hosts where this metadata must be private. It
does not expose tokens, full config, arguments, results, logs or artifacts. Gateway
admin/MCP bearer credentials remain exclusively in the backend; downstream secrets
are not forwarded to it. Its fixed gateway URL is not a viewer-controlled proxy.
Host/Origin/fetch-site checks mitigate browser cross-origin access and DNS rebinding;
CSP blocks inline scripts, external assets and framing. Untrusted descriptions are
inserted as text. This is not an authorization boundary against other local processes.
