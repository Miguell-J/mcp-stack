# Quickstart

Run make bootstrap, make up, make health and make tools as described in README.
The dependency source is immutable, official and clean; each project installs its
own lock. Bootstrap never silently changes an existing revision.

For an intentional audited update: python3 scripts/bootstrap.py --update-dependency.
A --ref override is for evaluation and emits a warning when it differs from the
recorded pin. Production builds use the recorded commit or versioned image only.

The core profile starts MCP One and enabled managed scientific servers. Only
MCP One publishes a loopback endpoint and joins the entrance network. Native
backends remain on the internal scientific network. The dev profile adds a test
runner; observability adds an optional OTel collector.

```bash
docker compose --profile core --profile dev build test-runner
docker compose --profile core --profile dev run --rm test-runner
# Optional; set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT in the environment first.
docker compose --profile core --profile observability up -d --build --wait
```

GET /health is liveness and GET /ready reports useful routing availability.
make health reads /status; a downstream outage need not restart a healthy hub.
Tool execution is always MCP /mcp, not an administrative REST endpoint.

Use make down to stop this project. There are no persistent application data
volumes. Configuration, virtual environments and dependency checkouts remain.
