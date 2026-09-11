"""Small sequential direct-versus-gateway smoke benchmark; no performance claims."""

import argparse
import asyncio
import json
import math
import platform
import statistics
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from mcp import Client


async def measure(direct_url: str, gateway_url: str, count: int = 100) -> dict[str, Any]:
    samples: dict[str, list[float]] = {"direct": [], "gateway": []}
    async with Client(direct_url, cache=None) as direct, Client(gateway_url, cache=None) as gateway:
        for client in (direct, gateway):
            await client.list_tools()
            for _ in range(10):
                result = await client.call_tool("demo.echo", {"message": "benchmark"})
                if result.is_error:
                    raise RuntimeError("benchmark warmup failed")
        for index in range(count):
            order = [("direct", direct), ("gateway", gateway)]
            if index % 2:
                order.reverse()
            for name, client in order:
                started = perf_counter()
                result = await client.call_tool("demo.echo", {"message": "benchmark"})
                elapsed = (perf_counter() - started) * 1000
                if result.is_error:
                    raise RuntimeError("benchmark call failed")
                samples[name].append(elapsed)
    summaries = {
        name: {
            "count": len(values),
            "medianMs": round(statistics.median(values), 3),
            "p95Ms": round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 3),
        }
        for name, values in samples.items()
    }
    return {
        "at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "method": "10 warmups per path; alternating sequential calls; nearest-rank p95",
        "caveat": "Development smoke benchmark. No load, concurrency or scientific rigor.",
        "results": summaries,
        "medianOverheadMs": round(
            summaries["gateway"]["medianMs"] - summaries["direct"]["medianMs"], 3
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct", required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000:
        parser.error("count must be between 1 and 10000")
    print(json.dumps(asyncio.run(measure(args.direct, args.gateway, args.count)), indent=2))
