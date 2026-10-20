"""Isolated live UI fixture. Never talks to or restarts the operator's gateway."""

import asyncio
import os
from datetime import UTC, datetime

from mcp_stack.config import load_config
from services.dashboard.app import create_app
from services.dashboard.monitor import Catalog, GatewayStatus, Monitor, ToolContract, ToolSummary


class FixtureMonitor(Monitor):
    async def run(self) -> None:
        while True:
            await asyncio.sleep(60)


def fixture_app():
    config = load_config()
    config.dashboard.cordis_snapshot_dir = os.environ["CORDIS_TEST_EXPORT"]
    config.dashboard.poll_seconds = 2
    observer = FixtureMonitor(config)
    at = datetime.now(UTC).isoformat()
    observer.status = GatewayStatus(
        version="fixture",
        ready=True,
        generation=1,
        tools=1,
        servers={
            server.id: {
                "state": "ONLINE",
                "catalogAvailable": True,
                "readyToRoute": True,
                "stale": False,
                "catalogAgeSeconds": 0,
                "tools": 1,
                "circuit": "CLOSED",
            }
            for server in config.enabled_servers
        },
    )
    observer.status_error = observer.metrics_error = None
    observer.status_at = at
    observer.catalog = Catalog(
        available=True,
        observed_at=at,
        tools=[
            ToolSummary(
                name="demo.fixture",
                description="Synthetic catalog for isolated UI validation",
                input_schema=True,
                output_schema=True,
            )
        ],
    )
    observer.contracts = {
        "demo.fixture": ToolContract(
            name="demo.fixture",
            description="Synthetic contract",
            inputSchema={"type": "object"},
            outputSchema={"type": "object", "properties": {"count": {"type": "integer"}}},
        )
    }
    return create_app(config, observer)
