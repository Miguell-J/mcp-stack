from mcp_stack.config import load_config

if __name__ == "__main__":
    config = load_config()
    if config.dashboard.enabled:
        print(f"Local monitoring dashboard: {config.dashboard.url}")
