# Thin Python scientific adapter

This is a runnable dependency-injection example. `domain_port.py` defines the
library boundary; `adapter.py` owns MCP, schemas and scientific serialization.
The injected library itself imports no MCP infrastructure.

From the stack root:

```bash
PYTHONPATH=templates/python_scientific_mcp/src .venv/bin/python -m pytest templates/python_scientific_mcp/tests -q
PYTHONPATH=templates/python_scientific_mcp/src .venv/bin/uvicorn example_scientific_mcp.adapter:create_app --factory --host 127.0.0.1 --port 8090
docker build -f templates/python_scientific_mcp/Dockerfile -t example-scientific-mcp:0.1.0 .
```

For a new independent repository, rename package/tools, inject its actual library,
pin the shared contract from a versioned wheel or Git commit, replace the local
uv path, and generate its own uv.lock. The Dockerfile here deliberately reuses
the stack's locked runtime for a smoke build; an independent server should have
its own pinned base/build. Enable OTLP export with an OTel provider/exporter at
the executable boundary, never inside domain functions. SDK tracing propagates
W3C context automatically. Log tool name, status and trace IDs, never inputs.

Every new scientific tool needs a bounded input signature, a concrete
`ScientificResult[T]` output annotation and contract tests. `Annotated` lets the
SDK derive outputSchema while retaining a concise human summary in content.
