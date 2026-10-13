---
name: stack-integration
description: Safely enroll and validate an independent native MCP server through manifests, rendering and pinned-gateway integration.
---

# stack-integration

Run from this repository root. Follow [adding a server](../../../docs/adding-a-server.md); inspect existing manifests before adding anything.

1. Verify the upstream library remains independent of MCP; the adapter imports the library.
2. Use config/servers.d manifests and existing schema/render scripts. Run `make validate render`; never hand-edit generated config or alter the MCP One pin implicitly.
3. Run `make test-template test-contract test-integration test-e2e` and check schemas and scientific results.
4. For a running stack, run `make health tools` and `STACK_ENDPOINT=http://127.0.0.1:8765/mcp make test-e2e`.
5. For Inspector use [development validation](../../../docs/development-validation.md). Do not duplicate registry, routing or circuit logic.

Preserve dirty checkouts, inspect environment-specific Compose overrides, keep public ports on loopback and disclose checks you could not run.
