# Security

## Threat model

This MVP is for a single trusted local user. Untrusted websites must not reach
the MCP endpoint through DNS rebinding, clients must not smuggle unbounded payloads,
and downstream catalogs/results must not trigger arbitrary schema retrieval.
Manifest authors and installed domain libraries are trusted executable-code
operators. This is not a public multi-user authorization system or a sandbox for
hostile scientific code. A malicious downstream may still consume its own CPU.

The only host binding is loopback. Only the edge joins the non-internal entrance
network needed for Docker port publishing; scientific services remain isolated.
SDK Host/Origin checks are enabled with explicit
allowlists. The bridge and hub are on an internal network without published ports
or external egress. All core containers run uid/gid 10001, drop capabilities, have
no-new-privileges, read-only filesystems and bounded tmpfs. No Docker socket, host
home, privileged flag or broad host filesystem mount is used.

Optional local bearer verification uses constant-time comparison at the edge.
This is a local shared-secret gate, not MCP OAuth authorization. Remote deployment
requires HTTPS, an MCP-compliant OAuth resource server and per-user policy; do not
publish the current localhost configuration to the Internet. Tool annotations
do not grant permissions. Authentication happens before request parsing.

Secrets come from named environment variables, never config YAML. .env is ignored.
Downstream credentials must be available in the bridge and are forwarded only to
the explicitly configured server. No redirects, ambient HTTP proxy settings or
arbitrary URI downloads are used. Logs omit arguments, results and tokens.

## Bounds

- 1 MiB default HTTP request/result cap, with chunked request checks.
- Downstream streams are bounded before SDK parsing; compressed responses are
  rejected to make the bound effective. Standard uncompressed JSON/SSE is supported.
- 128 KiB per schema, depth 32, 256 aggregate tools by default.
- External $ref/$dynamicRef, schema base URI changes and older dialect declarations
  are rejected before use. Only local $defs references are allowed. The SDK also
  uses an explicit reference registry rather than network fetching.
- Tool arguments and runtime results validate against their concrete schemas.
- Explicit nested timeouts: downstream < MCP One bridge timeout < edge timeout.
- Numerical representations reject NaN/Infinity and cap inline components.

Schema validation is bounded in size/depth but is not an isolation boundary for
adversarial exponential JSON Schemas or regular expressions. Only enroll trusted
scientific adapters; execution isolation/CPU quotas need a separate design before
accepting arbitrary third-party catalogs. Rate limiting is MCP One's process-local
per-IP limiter; all edge calls share the same internal client identity.

ArtifactReference describes a handle, not authorization to fetch a URI. Its future
resolver must enforce scheme/host allowlists, byte budgets and ownership checks.
