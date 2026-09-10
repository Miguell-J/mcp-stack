FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.13
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY src/ src/
COPY services/ services/
RUN uv sync --locked --no-dev --no-editable
COPY config/ config/
COPY scripts/ scripts/
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin stack
USER 10001:10001
CMD ["uvicorn", "services.gateway_edge.edge:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

FROM runtime AS mcp-one
# Original upstream files, taken only from the pinned bootstrap checkout.
COPY .deps/mcp-one/src/ /opt/mcp-one/src/
ENV PYTHONPATH=/opt/mcp-one/src
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM runtime AS development
USER root
RUN uv sync --locked --no-editable
COPY tests/ tests/
RUN chown -R 10001:10001 /app
USER 10001:10001
CMD ["python", "-m", "pytest", "tests/e2e", "-q"]
