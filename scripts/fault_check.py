"""Stop/restart the configured mock container and prove failure plus recovery."""

import asyncio
import os
import subprocess

import httpx
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mcp_stack.config import load_config
from mcp_stack.wire import INFRA_ERROR_META


async def main() -> None:
    config = load_config()
    url = config.gateway.endpoint
    token = os.getenv(config.gateway.token_env) if config.gateway.token_env else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    service = next(s.id for s in config.enabled_servers if s.id == "mock-scientific-mcp")
    command = ["docker", "compose", "--profile", "core"]
    async with (
        httpx2.AsyncClient(headers=headers, trust_env=False) as native_http,
        Client(streamable_http_client(url, http_client=native_http), cache=None) as client,
    ):
        await client.list_tools()
        try:
            subprocess.run([*command, "stop", service], check=True)
            failure = await client.call_tool("demo.echo", {"message": "mark offline"})
            async with httpx.AsyncClient(headers=headers, trust_env=False) as http:
                response = await http.get(url.removesuffix("/mcp") + "/ready", timeout=20)
                assert response.status_code == 503, response.text
            failure = await client.call_tool("demo.echo", {"message": "offline check"})
            assert failure.is_error and failure.meta is not None
            assert failure.meta[INFRA_ERROR_META]["category"] == "infrastructure"
            print("PASS: stopped mock -> readiness 503 and infrastructure isError")
        finally:
            subprocess.run([*command, "start", service], check=True)
        async with httpx.AsyncClient(headers=headers, trust_env=False) as http:
            for _ in range(40):
                response = await http.get(url.removesuffix("/mcp") + "/ready", timeout=20)
                if response.status_code == 200:
                    break
                await asyncio.sleep(0.5)
            else:
                raise RuntimeError("mock did not recover")
        await client.list_tools()
        result = await client.call_tool("demo.echo", {"message": "recovered"})
        assert not result.is_error
        print("PASS: restarted mock -> readiness 200 and successful native tool call")


if __name__ == "__main__":
    asyncio.run(main())
