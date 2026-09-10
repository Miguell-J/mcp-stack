"""Versioned, bounded scientific representations; no mathematical algorithms."""

from enum import StrEnum
from math import prod
from typing import Annotated, Any, Literal, Self

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, JsonValue, model_validator

CONTRACT_VERSION = 1
FiniteNumber = Annotated[float, Field(allow_inf_nan=False, strict=True)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_max_length=16384)


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    NOT_CHECKED = "not_checked"


class DiagnosticWarning(ContractModel):
    code: str = Field(min_length=1, max_length=128)
    severity: Severity
    message: str
    path: str | None = None
    details: dict[str, JsonValue] | None = None


class DiagnosticCheck(ContractModel):
    name: str
    status: CheckStatus
    value: JsonValue = None
    expected: JsonValue = None
    tolerance: Annotated[FiniteNumber, Field(ge=0)] | None = None
    details: dict[str, JsonValue] | None = None


class NumericalDiagnostics(ContractModel):
    iterations: int | None = Field(default=None, ge=0)
    residual: FiniteNumber | None = None
    condition_number: FiniteNumber | None = None
    converged: bool | None = None


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class Diagnostics(ContractModel):
    warnings: list[DiagnosticWarning] = Field(default_factory=list, max_length=100)
    checks: list[DiagnosticCheck] = Field(default_factory=list, max_length=100)
    numerical: NumericalDiagnostics | None = None
    completeness: Completeness | None = None


class ScientificContext(ContractModel):
    assumptions: list[str] | None = None
    coordinates: list[str] | None = None
    parameters: dict[str, JsonValue] | None = None
    conventions: dict[str, str] | None = None
    units: dict[str, str] | None = None
    domain: str | None = None


class Provenance(ContractModel):
    library: str
    library_version: str
    backend: str | None = None
    backend_version: str | None = None
    algorithm: str | None = None
    precision: str | None = None
    deterministic: bool | None = None
    seed: int | None = None


class ScientificResult[T](ContractModel):
    data: T
    context: ScientificContext | None = None
    diagnostics: Diagnostics | None = None
    provenance: Provenance | None = None


class SymbolicExpression(ContractModel):
    expression: str = Field(min_length=1)
    format: str = Field(min_length=1, max_length=64)
    latex: str | None = None
    symbols: list[str] = Field(default_factory=list, max_length=1024)


Component = FiniteNumber | SymbolicExpression


class Scalar(ContractModel):
    kind: Literal["scalar"] = "scalar"
    value: Component


class Vector(ContractModel):
    kind: Literal["vector"] = "vector"
    components: list[Component] = Field(min_length=1, max_length=4096)
    basis: list[str] | None = None

    @model_validator(mode="after")
    def matching_basis(self) -> Self:
        if self.basis is not None and len(self.basis) != len(self.components):
            raise ValueError("basis and vector dimensions differ")
        return self


class Matrix(ContractModel):
    kind: Literal["matrix"] = "matrix"
    shape: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]]
    components: list[list[Component]] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def matching_shape(self) -> Self:
        rows, columns = self.shape
        if prod(self.shape) > 4096:
            raise ValueError("large matrices require ArtifactReference")
        if len(self.components) != rows or any(len(row) != columns for row in self.components):
            raise ValueError("matrix components do not match shape")
        return self


class SparseComponent(ContractModel):
    index: list[Annotated[int, Field(ge=0)]] = Field(max_length=12)
    value: Component


class Tensor(ContractModel):
    kind: Literal["tensor"] = "tensor"
    rank: int = Field(ge=0, le=12)
    shape: list[Annotated[int, Field(gt=0)]] = Field(max_length=12)
    variance: list[Literal["covariant", "contravariant"]] = Field(max_length=12)
    representation: Literal["dense", "sparse"]
    components: list[Component] | list[SparseComponent] = Field(max_length=4096)

    @model_validator(mode="after")
    def matching_shape(self) -> Self:
        if len(self.shape) != self.rank or len(self.variance) != self.rank:
            raise ValueError("rank, shape and variance must agree")
        if self.representation == "dense":
            if len(self.components) != prod(self.shape) or any(
                isinstance(c, SparseComponent) for c in self.components
            ):
                raise ValueError("dense tensors use flat row-major components matching shape")
        else:
            seen: set[tuple[int, ...]] = set()
            for c in self.components:
                if not isinstance(c, SparseComponent) or len(c.index) != self.rank:
                    raise ValueError("sparse tensors require indexed components")
                key = tuple(c.index)
                if key in seen or any(i >= n for i, n in zip(c.index, self.shape, strict=True)):
                    raise ValueError("duplicate or out-of-bounds sparse component")
                seen.add(key)
        return self


class Equation(ContractModel):
    lhs: Component
    rhs: Component
    relation: Literal["eq", "lt", "le", "gt", "ge"] = "eq"


class ArtifactReference(ContractModel):
    uri: AnyUrl
    media_type: str
    name: str
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    description: str | None = None


class ErrorCategory(StrEnum):
    DOMAIN = "domain"
    INFRASTRUCTURE = "infrastructure"


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    DEGENERATE_STRUCTURE = "DEGENERATE_STRUCTURE"
    NON_CONVERGENCE = "NON_CONVERGENCE"
    NUMERICAL_INSTABILITY = "NUMERICAL_INSTABILITY"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    DOWNSTREAM_UNAVAILABLE = "DOWNSTREAM_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ScientificError(ContractModel):
    code: ErrorCode
    category: ErrorCategory
    message: str
    path: str | None = None
    retryable: bool = False
    details: dict[str, JsonValue] | None = None


def schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Generate the wire schema from its actual response model."""
    schema = model.model_json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema
