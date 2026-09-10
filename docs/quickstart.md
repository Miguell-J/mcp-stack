# Quickstart

Use the commands in README. Bootstrap creates an isolated virtualenv, resolves
only the committed lock and clones the official dependency if absent. Existing
dirty or differently pinned dependencies cause a clear failure.

To intentionally change the dependency, first audit the candidate, record its
full commit in stack.yaml and update the compatibility docs, then run:

```bash
.venv/bin/python scripts/bootstrap.py --update-dependency
make test-integration
```

`--ref TAG_OR_COMMIT` supports local evaluation; it prints the resolved commit and
warns when it differs from stack.yaml. Do not distribute builds from an override.

## Profiles

`make up` selects core: edge, hub, bridge and enabled managed scientific servers.
Only the edge port is published. The internal network intentionally blocks Internet
egress. A future remote MCP requires an explicit, documented egress change.

`dev` adds a disposable test-runner with the same locked dependencies:

```bash
docker compose --profile core --profile dev build test-runner
docker compose --profile core --profile dev run --rm test-runner
```

`observability` adds only an OTel Collector. Set
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces` in .env:

```bash
docker compose --profile core --profile observability up -d --build --wait
docker compose --profile observability logs otel-collector
```

The collector uses a console/debug exporter for development, not durable storage.
No host ports are required. Remove the endpoint or disable the profile to stop export.

Health is active and aggregate at /health and /ready; /live only checks the edge
process. Docker edge liveness intentionally does not depend on downstreams, so
an outage does not restart a healthy edge. `make health` reports downstream failures.

Stop with make down; it removes stack containers/network but not source, virtualenv
or dependency checkout. The stack has no persistent data volume.
