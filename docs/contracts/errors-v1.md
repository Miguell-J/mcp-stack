# Errors v1

| Category | Native representation | Examples |
| --- | --- | --- |
| Protocol | SDK JSON-RPC/HTTP error | malformed JSON, invalid MCP method/parameters/version, unknown tool (-32602) |
| Infrastructure | CallToolResult isError=true with category=infrastructure | offline downstream, timeout, invalid downstream result/schema |
| Domain/tool | CallToolResult isError=true with category=domain | invalid domain, singular structure, non-convergence, invalid tool arguments |

Domain/scientific descriptors live under `_meta["io.github.miguell-j.scientific/error"]`.
Fields: code, category, message, optional path/details and retryable. The human
content includes a short code/message; automation reads the descriptor. Successful
outputSchema applies only to successful results: an error does not pretend to be
a scientific T and normally omits structuredContent. There is no success=false
external envelope. Invalid argument shape for a known tool is a domain/tool
failure; malformed protocol parameters remain an SDK protocol error.

Codes: INVALID_ARGUMENT, INVALID_DOMAIN, DEGENERATE_STRUCTURE, NON_CONVERGENCE,
NUMERICAL_INSTABILITY, UNSUPPORTED_OPERATION, RESOURCE_NOT_FOUND,
DOWNSTREAM_UNAVAILABLE, TIMEOUT, INTERNAL_ERROR.

MCP One preserves native domain errors unchanged. Infrastructure/gateway errors
use the separate io.github.miguell-j.mcp-one/error namespace and codes such as
CALL_TIMEOUT, SERVER_UNAVAILABLE and CIRCUIT_OPEN. They are not ScientificError
instances and must not be interpreted as scientific diagnostics. Domain isError
never opens the infrastructure circuit. There is no REST status/envelope translation.
