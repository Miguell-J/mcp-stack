from mcp_stack.config import load_config

if __name__ == "__main__":
    config = load_config()
    print(f"Configuration valid: {len(config.enabled_servers)} enabled server(s)")
