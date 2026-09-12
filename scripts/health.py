import argparse
import asyncio
import os
import sys

import httpx

from mcp_stack.config import load_config


async def main(wait_seconds: float = 0) -> int:
    config = load_config()
    endpoint = os.getenv("STACK_ENDPOINT", config.gateway.endpoint)
    token = os.getenv(config.gateway.admin_token_env) if config.gateway.admin_token_env else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    deadline = asyncio.get_running_loop().time() + wait_seconds
    async with httpx.AsyncClient(trust_env=False, timeout=20, headers=headers) as client:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            timeout = min(20, max(0.001, remaining)) if wait_seconds else 20
            try:
                response = await client.get(
                    endpoint.removesuffix("/mcp") + "/status", timeout=timeout
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if not wait_seconds or code in {401, 403} or remaining <= 0:
                    print(f"mcp-stack unavailable ({code or 'unreachable'})")
                    return 1
            else:
                if data["ready"] or not wait_seconds or remaining <= 0:
                    print(f"mcp-stack {'ready' if data['ready'] else 'not ready'}")
                    for service, status in data["servers"].items():
                        print(f"{service} {status['state']}")
                    return 0 if data["ready"] else 1
            await asyncio.sleep(min(0.5, max(0, deadline - asyncio.get_running_loop().time())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-seconds", type=float, default=0)
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 300:
        parser.error("wait-seconds must be between 0 and 300")
    sys.exit(asyncio.run(main(args.wait_seconds)))
