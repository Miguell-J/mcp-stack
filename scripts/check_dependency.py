"""Fail before a source build can accidentally package a different upstream."""

import subprocess
from pathlib import Path

from mcp_stack.config import load_config


def check() -> None:
    config = load_config()
    if config.mcp_one.image:
        print(f"MCP One image: {config.mcp_one.image}")
        return
    path = Path(".deps/mcp-one")
    if not (path / ".git").exists():
        raise SystemExit("MCP One checkout missing; run make bootstrap")
    origin = subprocess.check_output(
        ["git", "-C", str(path), "remote", "get-url", "origin"], text=True
    ).strip()
    if origin != config.mcp_one.url:
        raise SystemExit("MCP One origin is not the official repository")
    head = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
    if status or head != config.mcp_one.ref:
        raise SystemExit("MCP One checkout is dirty or does not match the configured immutable pin")
    print(f"Verified MCP One source pin: {head}")


if __name__ == "__main__":
    check()
