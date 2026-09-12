# Troubleshooting

| Symptom | Check |
| --- | --- |
| Bootstrap refuses checkout | Check official origin, dirty files and full configured pin; explicit --update-dependency switches clean revisions |
| Native package import fails | Reinstall that checkout's uv.lock; verify the selected revision is native |
| Docker permission denied | Permit local Docker access; containers need no socket mount |
| Port allocated | Change gateway.port, render, restart and regenerate Codex instructions |
| Empty catalog | Read /status; invalid schemas/collisions are rejected, transient failures may retain stale definitions |
| /ready 503, /health 200 | The hub is alive but lacks the minimum useful routes |
| CALL_TIMEOUT | Review downstream call budget; do not blindly replay mutating tools |
| CIRCUIT_OPEN | Wait the configured reset; one actual call probes recovery |
| DOWNSTREAM_PROTOCOL_ERROR | Inspect catalog/outputSchema and sanitized logs |
| AUTH_FAILED | Check the proper upstream/admin/downstream environment reference |
| Codex sees REST migration notice | Register /mcp directly on MCP One |
| Collector unavailable | Enable its profile or unset OTEL_EXPORTER_OTLP_TRACES_ENDPOINT |
| Tests stall in sandbox | Real SDK tests need loopback/IPC and child-process permissions |

make test-integration injects faults only into its own fixture processes and cleans
them up. make fault-check stops/restarts only this Compose project's mock and
restores it in a finally block. Historical REST problems are archived in docs/history.
