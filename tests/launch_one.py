"""Test-only launch of unmodified upstream app with a temporary config path."""

import os
from pathlib import Path

import uvicorn
from app import main

main.CONFIG_PATH = Path(os.environ["MCP_ONE_TEST_CONFIG"])
main.config = main.load_runtime_config()
uvicorn.run(main.app, host="127.0.0.1", port=int(os.environ["MCP_ONE_TEST_PORT"]), access_log=False)
