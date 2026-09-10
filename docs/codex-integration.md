# Codex integration

One server entry exposes the whole stack:

```bash
make codex-config
codex mcp add scientific-stack --url http://127.0.0.1:8765/mcp
codex mcp list
```

Equivalent TOML:

```toml
[mcp_servers.scientific-stack]
url = "http://127.0.0.1:8765/mcp"
```

For the optional local bearer token, define MCP_STACK_TOKEN in the environment
of both Codex and the stack, then use:

```bash
codex mcp add scientific-stack --url http://127.0.0.1:8765/mcp --bearer-token-env-var MCP_STACK_TOKEN
```

The TOML equivalent adds `bearer_token_env_var = "MCP_STACK_TOKEN"`.
No script edits ~/.codex/config.toml. MCP One's own REST URL must not be registered.
The installed `codex mcp add --help` was checked during implementation and confirms
these options. `codex mcp list` lists configuration; use `/mcp` in a Codex session
and the E2E client tests to check actual tool availability.

The [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
documents Streamable HTTP and shared config.toml settings. There is no hard Codex
version requirement: use a build supporting --url. The official SDK handles
legacy handshake compatibility; the stack does not implement a second protocol.
