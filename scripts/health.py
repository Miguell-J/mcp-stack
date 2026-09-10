import asyncio
import os
import sys

import httpx

from mcp_stack.config import load_config


async def main() -> int:
    config = load_config()
    endpoint = os.getenv("STACK_ENDPOINT", config.gateway.endpoint)
    token = os.getenv("MCP_STACK_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=20, headers=headers) as client:
            response = await client.get(endpoint.removesuffix("/mcp") + "/health")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 503:
            print(f"mcp-stack health request rejected: HTTP {exc.response.status_code}")
            return 1
        data = exc.response.json()
    except httpx.HTTPError:
        print("mcp-stack unreachable")
        return 1
    print(f"mcp-stack {data['status']}")
    for service, status in data["services"].items():
        print(f"{service} {status}")
    return 0 if data["status"] == "healthy" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
