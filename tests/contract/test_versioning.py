from pathlib import Path

from scientific_mcp_contracts import CONTRACT_VERSION, ScientificResult

from scripts.generate_contract_docs import document
from services.mock_scientific_mcp.app import EchoData


def test_contract_v1_shape_and_old_minimal_result():
    assert CONTRACT_VERSION == 1
    schema = ScientificResult[EchoData].model_json_schema()
    assert set(schema["properties"]) == {"data", "context", "diagnostics", "provenance"}
    assert schema["required"] == ["data"]
    old = {"data": {"message": "v1 minimal"}}
    assert ScientificResult[EchoData].model_validate(old).model_dump(exclude_none=True) == old


def test_documentation_example_is_generated_from_runtime_model():
    assert Path("docs/contracts/example-v1.md").read_text() == document()
