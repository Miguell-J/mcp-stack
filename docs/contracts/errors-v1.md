# Errors v1

| Category | Native representation | Examples |
| --- | --- | --- |
| Protocol | SDK JSON-RPC/HTTP error | malformed JSON, invalid MCP method/parameters/version, unknown tool (-32602) |
| Infrastructure | CallToolResult isError=true with category=infrastructure | offline bridge/downstream, timeout, invalid downstream result/schema |
| Domain/tool | CallToolResult isError=true with category=domain | invalid domain, singular structure, non-convergence, invalid tool arguments |

Stable descriptors live under `_meta["io.github.miguell-j.scientific/error"]`.
Fields: code, category, message, optional path/details and retryable. The human
content includes a short code/message; automation reads the descriptor. Successful
outputSchema applies only to successful results: an error does not pretend to be
a scientific T and normally omits structuredContent. There is no success=false
external envelope. Invalid argument shape for a known tool is a domain/tool
failure; malformed protocol parameters remain an SDK protocol error.

Codes: INVALID_ARGUMENT, INVALID_DOMAIN, DEGENERATE_STRUCTURE, NON_CONVERGENCE,
NUMERICAL_INSTABILITY, UNSUPPORTED_OPERATION, RESOURCE_NOT_FOUND,
DOWNSTREAM_UNAVAILABLE, TIMEOUT, INTERNAL_ERROR.

The bridge returns HTTP 200 to MCP One when native MCP execution completed,
including native domain isError. Infrastructure failures use HTTP 502/503/504 so
the existing hub breaker records a failed request. The edge maps known legacy
tokens/status codes to stable codes. Free-form legacy exception strings are never
shown to the external client. Nested AnyIO exception groups are classified by
typed underlying exceptions, not by matching their messages.

The hub's own call-success counter therefore means successful transport execution,
not scientific success. The edge logs isError with the final native semantics.
