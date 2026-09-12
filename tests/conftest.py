import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml

from mcp_stack.config import StackConfig, load_config
from mcp_stack.render import one_config

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LiveStack:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.processes = {}
        self.logs = {}
        self.ports = {name: free_port() for name in ("mock", "one")}
        data = load_config(ROOT / "config/stack.yaml").model_dump()
        data["servers"] = [s for s in data["servers"] if s["enabled"]]
        data["servers"][0]["transport"].update(
            url=f"http://127.0.0.1:{self.ports['mock']}/mcp", timeout_seconds=0.8
        )
        data["servers"][0]["health"].update(
            url=f"http://127.0.0.1:{self.ports['mock']}/health", timeout_seconds=0.3
        )
        data["gateway"].update(
            refresh_interval_seconds=0.5,
            circuit_breaker_reset_seconds=1,
        )
        self.config = StackConfig.model_validate(data)
        self.admin_url = f"http://127.0.0.1:{self.ports['one']}"
        self.url = self.admin_url + "/mcp"
        config_dir = directory / "config"
        (config_dir / "servers.d").mkdir(parents=True)
        servers = data.pop("servers")
        (config_dir / "stack.yaml").write_text(yaml.safe_dump(data))
        (config_dir / "servers.d/mock.yaml").write_text(yaml.safe_dump(servers[0]))
        self.one_config_path = directory / "one.yaml"
        self.one_config_path.write_text(yaml.safe_dump(one_config(self.config)))
        self.env = {
            **os.environ,
            "STACK_CONFIG": str(config_dir / "stack.yaml"),
            "MCP_STACK_TOKEN": "",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "",
        }

    def start(self, name: str) -> None:
        env = dict(self.env)
        if name == "one":
            source = Path(os.getenv("MCP_ONE_SOURCE", ROOT / ".deps/mcp-one")).resolve()
            env["MCP_ONE_CONFIG"] = str(self.one_config_path)
            command = [
                str(source / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "mcp_one.server:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.ports[name]),
                "--no-access-log",
            ]
            route = "/health"
        else:
            modules = {
                "mock": "services.mock_scientific_mcp.app",
            }
            if name == "mock" and "STACK_FAULT_FILE" in env:
                modules["mock"] = "tests.faulty_mcp"
            command = [
                sys.executable,
                "-m",
                "uvicorn",
                f"{modules[name]}:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.ports[name]),
                "--no-access-log",
            ]
            route = "/health" if name == "mock" else "/live"
        log = (self.directory / f"{name}.log").open("a")
        self.logs[name] = log
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        self.processes[name] = process
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError((self.directory / f"{name}.log").read_text())
            try:
                response = httpx.get(f"http://127.0.0.1:{self.ports[name]}{route}", timeout=0.2)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"{name} did not start: {(self.directory / f'{name}.log').read_text()}")

    def stop(self, name: str) -> None:
        process = self.processes.pop(name, None)
        if process:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            self.logs.pop(name).close()

    def close(self) -> None:
        for name in list(reversed(self.processes)):
            self.stop(name)


@pytest.fixture(scope="session")
def live_stack(tmp_path_factory):
    stack = LiveStack(tmp_path_factory.mktemp("scientific-stack"))
    try:
        for name in ("mock", "one"):
            stack.start(name)
        yield stack
    finally:
        stack.close()


@pytest.fixture
def endpoint(request):
    external = os.getenv("STACK_ENDPOINT")
    if external:
        return external
    return request.getfixturevalue("live_stack").url
