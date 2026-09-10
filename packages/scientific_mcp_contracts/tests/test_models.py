import math

import pytest
from jsonschema import Draft202012Validator
from pydantic import AnyUrl, ValidationError
from scientific_mcp_contracts import (
    ArtifactReference,
    CheckStatus,
    ContractModel,
    DiagnosticCheck,
    Diagnostics,
    DiagnosticWarning,
    Matrix,
    Provenance,
    Scalar,
    ScientificResult,
    Severity,
    SparseComponent,
    SymbolicExpression,
    Tensor,
    Vector,
    schema_for,
)


class CountData(ContractModel):
    count: int


def test_generic_roundtrip_and_generated_schema():
    model = ScientificResult[CountData](
        data=CountData(count=3),
        diagnostics=Diagnostics(
            warnings=[
                DiagnosticWarning(
                    code="APPROXIMATE",
                    severity=Severity.WARNING,
                    message="Approximation",
                    path="/data/count",
                    details={"order": 2},
                )
            ],
            checks=[DiagnosticCheck(name="count", status=CheckStatus.PASSED, value=3, expected=3)],
        ),
        provenance=Provenance(
            library="fixture",
            library_version="1.0.0",
            deterministic=True,
            precision="float64",
            seed=7,
        ),
    )
    encoded = model.model_dump(mode="json", exclude_none=True)
    assert ScientificResult[CountData].model_validate(encoded) == model
    schema = schema_for(ScientificResult[CountData])
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(encoded)
    assert schema["$defs"]["CountData"]["properties"]["count"]["type"] == "integer"


@pytest.mark.parametrize(
    "payload",
    [{}, {"data": {}}, {"data": {"count": "bad"}}, {"data": {"count": 1}, "success": True}],
)
def test_invalid_results_rejected(payload):
    with pytest.raises(ValidationError):
        ScientificResult[CountData].model_validate(payload)


def test_warnings_are_not_free_text():
    with pytest.raises(ValidationError):
        Diagnostics.model_validate({"warnings": ["bad warning"]})
    with pytest.raises(ValidationError):
        DiagnosticCheck(name="check", status="maybe")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "3", True])
def test_numeric_scalars_reject_nonfinite_and_coercion(value):
    with pytest.raises(ValidationError):
        Scalar(value=value)


def test_symbolic_presentation_is_optional():
    expr = SymbolicExpression(expression="r**2*sin(theta)", format="sympy", symbols=["r", "theta"])
    assert expr.latex is None
    assert Scalar(value=expr).value.expression == expr.expression


def test_matrix_and_vector_dimensions():
    with pytest.raises(ValidationError):
        Matrix(shape=(2, 2), components=[[1.0]])
    with pytest.raises(ValidationError):
        Vector(components=[1.0, 2.0], basis=["x"])


def test_tensor_sparse_and_dense():
    tensor = Tensor(
        rank=2,
        shape=[10000, 10000],
        variance=["covariant", "contravariant"],
        representation="sparse",
        components=[SparseComponent(index=[1, 2], value=1.0)],
    )
    assert tensor.components[0].index == [1, 2]
    with pytest.raises(ValidationError):
        Tensor(
            rank=2,
            shape=[2, 2],
            variance=["covariant", "covariant"],
            representation="dense",
            components=[1.0],
        )
    with pytest.raises(ValidationError):
        Tensor(
            rank=1,
            shape=[2],
            variance=["covariant"],
            representation="sparse",
            components=[SparseComponent(index=[2], value=1.0)],
        )
    with pytest.raises(ValidationError):
        Tensor(
            rank=1,
            shape=[2],
            variance=["covariant"],
            representation="sparse",
            components=[SparseComponent(index=[1], value=1.0)] * 2,
        )


def test_artifact_reference():
    artifact = ArtifactReference(
        uri=AnyUrl("s3://bucket/trajectory"),
        media_type="application/x-parquet",
        name="trajectory",
        sha256="a" * 64,
        size_bytes=10000000,
    )
    assert artifact.model_dump(mode="json")["uri"] == "s3://bucket/trajectory"
