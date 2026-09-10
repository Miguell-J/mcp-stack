# Troubleshooting

| Symptom | Check |
| --- | --- |
| Bootstrap refuses an existing checkout | git -C .deps/mcp-one status; compare HEAD with stack.yaml; explicit --update-dependency only for a clean checkout |
| MCP One IndentationError | default upstream master is broken; use the audited immutable pin |
| Docker permission denied | start Docker and grant your user Docker access; no socket mount is needed |
| Port already allocated | change gateway.port in stack.yaml and run make render/up/codex-config |
| Codex sees no tools | use the native /mcp endpoint, make health, make tools; do not register MCP One /tools |
| 401 | set the same MCP_STACK_TOKEN in Codex and stack environments |
| Host/Origin rejected | use localhost; for a new internal server configure its exact SDK allowed hostname |
| DOWNSTREAM_UNAVAILABLE | inspect health, private hub metrics and bridge logs; circuit may be temporarily open |
| TIMEOUT | check backend duration; adjust downstream then outer timeout while preserving nesting |
| INTERNAL_ERROR with isError | response/schema/bridge contract failed; inspect error type in logs, not scientific data |
| Invalid catalog or missing server tools | missing outputSchema, external refs, duplicate normalized names or unhealthy downstream |
| Old tool still callable during outage | MCP One retains its registry; the edge call returns infrastructure error, not stale results |
| Collector exports fail | enable observability profile and set the full OTLP /v1/traces URL |
| Tests hang in a restricted sandbox | integration tests need loopback sockets and subprocess/thread support; run in an allowed local environment |

Run `make test-integration` for repeatable failures/recovery. The tests terminate
and restart only their own mock process and clean up all child processes.
To check actual containers use scripts/fault_check.py, which restores the mock
in a finally block. `make down` stops only this Compose project.
