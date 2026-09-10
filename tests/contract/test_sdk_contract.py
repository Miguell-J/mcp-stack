from jsonschema import Draft202012Validator
from mcp import Client
from scientific_mcp_contracts import ScientificResult

from mcp_stack.wire import validate_tool
from services.mock_scientific_mcp.app import EchoData, MatrixData, create_server


async def test_every_tool_has_concrete_output_schema_and_native_result():
    async with Client(create_server()) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert len(tools) == 5
        for tool in tools.values():
            validate_tool(tool)
        result = await client.call_tool("demo.identity_matrix", {"size": 2})
        typed = ScientificResult[MatrixData].model_validate(result.structured_content)
        assert typed.data.matrix.shape == (2, 2)
        assert result.is_error is False
        echoed = await client.call_tool("demo.echo", {"message": "roundtrip"})
        ScientificResult[EchoData].model_validate(echoed.structured_content)
        Draft202012Validator(tools["demo.echo"].output_schema).validate(echoed.structured_content)


async def test_resource_content_matches_reference():
    import hashlib

    async with Client(create_server()) as client:
        result = await client.call_tool("demo.artifact", {})
        artifact = result.structured_content["data"]["artifact"]
        resource = await client.read_resource(artifact["uri"])
        assert hashlib.sha256(resource.contents[0].text.encode()).hexdigest() == artifact["sha256"]
