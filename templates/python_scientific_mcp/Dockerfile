# Build from the mcp-stack root after make up has built this locked runtime image.
FROM mcp-stack:0.3.0
USER root
COPY templates/python_scientific_mcp/ /opt/adapter/
RUN uv pip install --python /app/.venv/bin/python --no-deps /opt/adapter
USER 10001:10001
CMD ["uvicorn", "example_scientific_mcp.adapter:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
