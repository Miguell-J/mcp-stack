"""Validate advertised wire schemas and semantic model invariants separately."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError
from mcp import Client
from pydantic import ValidationError as ModelError
from scientific_mcp_contracts import Matrix, ScientificResult

from services.mock_scientific_mcp.app import EchoData, create_server


@pytest.mark.parametrize("mutation", ["missing_data", "wrong_type", "unknown_field", "provenance"])
async def test_invalid_scientific_results_fail_the_advertised_output_schema(mutation):
    async with Client(create_server(), cache=None) as client:
        tool = next(t for t in (await client.list_tools()).tools if t.name == "demo.echo")
        result = await client.call_tool("demo.echo", {"message": "contract"})
        payload = deepcopy(result.structured_content)
        if mutation == "missing_data":
            payload.pop("data")
        elif mutation == "wrong_type":
            payload["data"]["message"] = ["untyped"]
        elif mutation == "unknown_field":
            payload["authority"] = "bypass-scientific-contract"
        else:
            payload["provenance"] = {"library": "fixture", "library_version": "1", "seed": []}
        with pytest.raises(ValidationError):
            Draft202012Validator(tool.output_schema).validate(payload)
        with pytest.raises(ModelError):
            ScientificResult[EchoData].model_validate(payload)


async def test_optional_context_diagnostics_and_provenance_remain_optional():
    async with Client(create_server(), cache=None) as client:
        tool = next(t for t in (await client.list_tools()).tools if t.name == "demo.echo")
        minimal = {"data": {"message": "minimal-v1"}}
        Draft202012Validator(tool.output_schema).validate(minimal)
        parsed = ScientificResult[EchoData].model_validate(minimal)
        assert parsed.context is parsed.diagnostics is parsed.provenance is None


def test_cross_field_matrix_invariants_require_semantic_validation():
    payload = {"kind": "matrix", "shape": [2, 2], "components": [[1.0]]}
    # JSON Schema cannot express this cross-field equality; adapters must validate models.
    Draft202012Validator(Matrix.model_json_schema()).validate(payload)
    with pytest.raises(ModelError, match="components do not match shape"):
        Matrix.model_validate(payload)
