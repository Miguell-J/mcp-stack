from example_scientific_mcp.adapter import create_server
from example_scientific_mcp.domain_port import LibraryDescription
from jsonschema import Draft202012Validator
from mcp import Client


class TestLibrary:
    def describe(self):
        return LibraryDescription("injected", "7.0.0", "Injected library")


async def test_injected_library_contract():
    async with Client(create_server(TestLibrary())) as client:
        tool = (await client.list_tools()).tools[0]
        result = await client.call_tool(tool.name, {})
        assert result.structured_content["provenance"]["library"] == "injected"
        assert result.structured_content["data"] == {"description": "Injected library"}
        Draft202012Validator(tool.output_schema).validate(result.structured_content)
