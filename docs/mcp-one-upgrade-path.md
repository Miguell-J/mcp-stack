# Migration to native MCP One

The temporary upgrade path is implemented. The current topology is Codex -> MCP
One /mcp -> native scientific MCP. services/gateway_edge and both compatibility
services were removed; their history remains available through Git and ADR 0002.

The 0.2 stack configuration removes one_url, bridge_url, legacy health retry/rate-limit
settings, request_timeout_seconds, catalog_ttl_seconds and REST field mappings.
Native MCP One owns retry/circuit/health policy. Actual per-server execution and
discovery budgets come from transport.timeout_seconds; catalog freshness is TTL zero.
Use gateway.discovery_attempts and refresh_interval_seconds. Config remains
strict: obsolete fields produce validation errors. Optional upstream and admin
secret references are gateway.token_env and gateway.admin_token_env.

1. Stop the previous deployment with its original Compose configuration.
2. Review/update the full MCP One commit in config/stack.yaml.
3. Run python3 scripts/bootstrap.py --update-dependency. Dirty checkouts are refused.
4. Run make render, make lint, make test-integration and make test-e2e.
5. Run make up, make health, make tools and external STACK_ENDPOINT E2E.
6. Keep the same public /mcp URL in Codex; its owner is now MCP One directly.

The scientific contract v1 and library adapters require no semantic changes.
Native results need no wrapper/unwrapper. _meta for infrastructure errors moves
from the scientific namespace to MCP One's namespace. Health is now explicitly
liveness at /health and useful-route readiness at /ready; make health reads the
administrative /status report. Prometheus /metrics now contains valid text.

Rollback uses the prior stack commit together with its original clean upstream
pin and generated Compose. Do not mix old REST config with a new native image.
The upstream docs/migration-to-native-mcp.md describes standalone REST migration.
