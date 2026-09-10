import json

from mcp_stack.config import load_config


def configuration() -> str:
    gateway = load_config().gateway
    endpoint = gateway.endpoint
    return (
        f"Endpoint: {endpoint}\nName: scientific-stack\n\n"
        f"codex mcp add scientific-stack --url {endpoint}\n"
        "codex mcp list\n\n"
        "[mcp_servers.scientific-stack]\n"
        f"url = {json.dumps(endpoint)}\n"
        "# For token authentication, add --bearer-token-env-var MCP_STACK_TOKEN to the command\n"
        '# or uncomment: bearer_token_env_var = "MCP_STACK_TOKEN"\n'
    )


if __name__ == "__main__":
    print(configuration())
