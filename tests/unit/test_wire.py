import pytest
from mcp.types import CallToolResult, TextContent, Tool

from mcp_stack.wire import ERROR_META, bounded_json, legacy_error, validate_result, validate_schema


@pytest.mark.parametrize(
    "legacy,code",
    [
        ("timeout", "TIMEOUT"),
        ("http_error_504", "TIMEOUT"),
        ("circuit_open", "DOWNSTREAM_UNAVAILABLE"),
        ("server_offline", "DOWNSTREAM_UNAVAILABLE"),
        ("http_error_502", "INTERNAL_ERROR"),
        ("tool_not_found", "RESOURCE_NOT_FOUND"),
    ],
)
def test_legacy_error_mapping(legacy, code):
    result = legacy_error(legacy)
    assert result.is_error
    assert result.meta[ERROR_META]["code"] == code
    assert result.meta[ERROR_META]["category"] == "infrastructure"
    assert result.structured_content is None


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "$ref": "https://attacker.invalid/schema"},
        {"type": "object", "$id": "https://attacker.invalid/"},
        {"type": "object", "properties": {"x": {"$dynamicRef": "file:///etc/passwd"}}},
        {"type": "array"},
        {"type": "object", "$schema": "http://json-schema.org/draft-07/schema#"},
    ],
)
def test_unsafe_schemas_rejected_without_dereferencing(schema):
    with pytest.raises(ValueError):
        validate_schema(schema, 131072, 32)


def test_payload_and_depth_limits():
    with pytest.raises(ValueError):
        bounded_json({"data": "x" * 4096}, 100)
    with pytest.raises(ValueError):
        bounded_json({"a": {"b": {"c": 1}}}, 1000, 2)


def test_invalid_runtime_response_rejected():
    tool = Tool(
        name="demo.echo",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"data": {"type": "integer"}},
            "required": ["data"],
        },
    )
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate_result(
            tool,
            CallToolResult(
                content=[TextContent(type="text", text="bad")],
                structured_content={"data": "not an integer"},
            ),
        )
