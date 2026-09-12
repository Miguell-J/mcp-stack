import asyncio
import os
import sys

import httpx

from mcp_stack.config import load_config


async def main() -> int:
    config = load_config()
    endpoint = os.getenv("STACK_ENDPOINT", config.gateway.endpoint)
    token = os.getenv(config.gateway.admin_token_env) if config.gateway.admin_token_env else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=20, headers=headers) as client:
            response = await client.get(endpoint.removesuffix("/mcp") + "/status")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        status = (
            exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else "unreachable"
        )
        print(f"mcp-stack unavailable ({status})")
        return 1
    print(f"mcp-stack {'ready' if data['ready'] else 'not ready'}")
    for service, status in data["servers"].items():
        print(f"{service} {status['state']}")
    return 0 if data["ready"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
