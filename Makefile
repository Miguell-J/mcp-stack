PY := .venv/bin/python
UV := .venv/bin/uv
COMPOSE := docker compose --profile core
export UV_CACHE_DIR := $(CURDIR)/.uv-cache
-include .env
export MCP_STACK_TOKEN
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT

.PHONY: bootstrap validate render up down restart logs health tools test test-contract test-integration test-e2e lint format codex-config test-template fault-check contract-docs
bootstrap:
	python3 scripts/bootstrap.py
validate:
	$(PY) scripts/validate_config.py
render: validate
	$(PY) scripts/render_config.py
up: render
	$(PY) scripts/check_dependency.py
	$(COMPOSE) up --build -d --wait --wait-timeout 180
	$(PY) scripts/dashboard_url.py
down:
	docker compose --profile core --profile dev --profile observability down --remove-orphans
restart:
	$(MAKE) down
	$(MAKE) up
logs:
	$(COMPOSE) logs --tail=100 -f
health:
	$(PY) scripts/health.py
tools:
	$(PY) scripts/tool_catalog.py
test:
	$(PY) -m pytest tests/unit tests/contract packages/scientific_mcp_contracts/tests -q
test-contract:
	$(PY) -m pytest tests/contract packages/scientific_mcp_contracts/tests -q
test-integration:
	$(PY) -m pytest tests/integration -q
test-e2e:
	$(PY) -m pytest tests/e2e -q
lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	.venv/bin/mypy
format:
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .
codex-config:
	$(PY) scripts/generate_codex_config.py
test-template:
	PYTHONPATH=templates/python_scientific_mcp/src $(PY) -m pytest templates/python_scientific_mcp/tests -q
fault-check:
	$(PY) scripts/fault_check.py
contract-docs:
	$(PY) scripts/generate_contract_docs.py
