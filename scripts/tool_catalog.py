import argparse
import asyncio
import json
import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mcp_stack.config import load_config


async def main(as_json: bool) -> None:
    config = load_config()
    url = os.getenv("STACK_ENDPOINT", config.gateway.endpoint)
    token = os.getenv(config.gateway.token_env) if config.gateway.token_env else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(headers=headers, trust_env=False) as http:
        async with Client(streamable_http_client(url, http_client=http), cache=None) as client:
            page = await client.list_tools()
            tools = list(page.tools)
            while page.next_cursor:
                page = await client.list_tools(cursor=page.next_cursor)
                tools.extend(page.tools)
            if as_json:
                print(
                    json.dumps(
                        [
                            t.model_dump(mode="json", by_alias=True, exclude_none=True)
                            for t in tools
                        ],
                        indent=2,
                    )
                )
                return
            namespace = None
            for tool in sorted(tools, key=lambda t: t.name):
                group = tool.name.partition(".")[0]
                if group != namespace:
                    print(group)
                    namespace = group
                print(f"  {tool.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json", action="store_true", help="Full schemas for documentation generation"
    )
    asyncio.run(main(parser.parse_args().json))
