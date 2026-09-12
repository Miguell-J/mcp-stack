import json

from mcp_stack.config import load_config


def configuration() -> str:
    gateway = load_config().gateway
    endpoint = gateway.endpoint
    auth_arg = f" --bearer-token-env-var {gateway.token_env}" if gateway.token_env else ""
    auth_config = (
        f"bearer_token_env_var = {json.dumps(gateway.token_env)}\n" if gateway.token_env else ""
    )
    return (
        f"Endpoint: {endpoint}\nName: scientific-stack\n\n"
        f"codex mcp add scientific-stack --url {endpoint}{auth_arg}\n"
        "codex mcp list\n\n"
        "[mcp_servers.scientific-stack]\n"
        f"url = {json.dumps(endpoint)}\n"
        f"{auth_config}"
    )


if __name__ == "__main__":
    print(configuration())
