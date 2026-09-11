"""Native MCP conversion and bounded validation at trust boundaries."""

import json
from typing import Any

from jsonschema import Draft202012Validator
from mcp.types import CallToolResult, TextContent, Tool
from pydantic import BaseModel
from scientific_mcp_contracts import (
    ErrorCategory,
    ErrorCode,
    ScientificError,
)

GATEWAY_META = "io.github.miguell-j.mcp-one/gateway"
ERROR_META = "io.github.miguell-j.scientific/error"
CONTRACT_META = "io.github.miguell-j.scientific/contract"
INFRA_ERROR_META = "io.github.miguell-j.mcp-one/error"


def result_for(model: BaseModel, summary: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=model.model_dump(mode="json", exclude_none=True),
        _meta={CONTRACT_META: {"family": "scientific-result", "version": 1}},
    )


def error_result(
    code: ErrorCode,
    category: ErrorCategory,
    message: str,
    *,
    retryable: bool = False,
) -> CallToolResult:
    error = ScientificError(code=code, category=category, message=message, retryable=retryable)
    return CallToolResult(
        content=[TextContent(type="text", text=f"{code.value}: {message}")],
        is_error=True,
        _meta={ERROR_META: error.model_dump(mode="json", exclude_none=True)},
    )


def bounded_json(value: Any, max_bytes: int, max_depth: int = 48) -> None:
    if len(json.dumps(value, allow_nan=False, separators=(",", ":")).encode()) > max_bytes:
        raise ValueError("JSON exceeds configured size limit")
    pending = [(value, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > max_depth:
            raise ValueError("JSON exceeds configured depth limit")
        if isinstance(node, dict):
            pending.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            pending.extend((v, depth + 1) for v in node)


def validate_schema(schema: dict[str, Any], max_bytes: int, max_depth: int) -> None:
    bounded_json(schema, max_bytes, max_depth)
    if schema.get("type") != "object":
        raise ValueError("scientific tool schema root must be an object")
    pending: list[Any] = [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"$ref", "$dynamicRef"}:
                    if not isinstance(value, str) or not value.startswith("#/$defs/"):
                        raise ValueError("only local $defs references are allowed")
                if key == "$id":
                    raise ValueError("schema base URI changes are not permitted")
                if key == "$schema" and value != "https://json-schema.org/draft/2020-12/schema":
                    raise ValueError("only JSON Schema 2020-12 is accepted")
                pending.append(value)
        elif isinstance(node, list):
            pending.extend(node)
    Draft202012Validator.check_schema(schema)


def validate_tool(tool: Tool, max_bytes: int = 131072, max_depth: int = 32) -> None:
    validate_schema(tool.input_schema, max_bytes, max_depth)
    if tool.output_schema is None:
        raise ValueError("scientific tools must advertise outputSchema")
    validate_schema(tool.output_schema, max_bytes, max_depth)
    properties = tool.output_schema.get("properties", {})
    if "data" not in properties or "data" not in tool.output_schema.get("required", []):
        raise ValueError("outputSchema must describe ScientificResult<T> with required data")
    if not any(key in properties["data"] for key in ("type", "$ref", "anyOf", "oneOf", "allOf")):
        raise ValueError("ScientificResult data requires a concrete schema")


def validate_result(tool: Tool, result: CallToolResult, max_bytes: int = 1048576) -> None:
    bounded_json(result.model_dump(mode="json", by_alias=True), max_bytes)
    if result.result_type != "complete":
        raise ValueError("multi-round results are outside this stateless adapter's contract")
    if result.is_error:
        error = (result.meta or {}).get(ERROR_META)
        if error is None:
            raise ValueError("scientific tool errors must include stable error metadata")
        ScientificError.model_validate(error)
    else:
        if result.structured_content is None or tool.output_schema is None:
            raise ValueError("successful scientific result requires structuredContent")
        Draft202012Validator(tool.output_schema).validate(result.structured_content)
