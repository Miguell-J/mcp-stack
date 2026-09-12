import pytest
from mcp.types import CallToolResult, TextContent, Tool

from mcp_stack.wire import bounded_json, validate_result, validate_schema


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
