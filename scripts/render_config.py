from pathlib import Path

from mcp_stack.config import load_config
from mcp_stack.render import render

if __name__ == "__main__":
    render(load_config(), Path.cwd())
    print("Generated .generated/{mcp-one,compose}.yaml and config/schemas/stack.schema.json")
