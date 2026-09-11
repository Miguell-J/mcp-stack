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

For optional local bearer authentication, set gateway.token_env: MCP_STACK_TOKEN
in config/stack.yaml and define MCP_STACK_TOKEN in the environment
of both Codex and the stack, then use:

```bash
codex mcp add scientific-stack --url http://127.0.0.1:8765/mcp --bearer-token-env-var MCP_STACK_TOKEN
```

The TOML equivalent adds `bearer_token_env_var = "MCP_STACK_TOKEN"`.
No script edits ~/.codex/config.toml. Register MCP One's native /mcp URL directly; no edge adapter is needed.
The installed `codex mcp add --help` was checked during implementation and confirms
these options. `codex mcp list` lists configuration; use `/mcp` in a Codex session
and the E2E client tests to check actual tool availability.

Validation also ran add, list and get --json with CLI 0.154.0 in a temporary
CODEX_HOME. The entry was enabled with streamable_http transport; the directory
was then removed. No permanent user configuration was changed.

The [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
documents Streamable HTTP and shared config.toml settings. There is no hard Codex
version requirement: use a build supporting --url. The official SDK handles
legacy handshake compatibility; the stack does not implement a second protocol.
