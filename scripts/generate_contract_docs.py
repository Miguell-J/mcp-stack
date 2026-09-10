"""Render executable contract examples directly from the models used by tools."""

import json
from pathlib import Path

from scientific_mcp_contracts import Provenance, ScientificResult

from mcp_stack.wire import result_for
from services.mock_scientific_mcp.app import EchoData


def document() -> str:
    result = result_for(
        ScientificResult[EchoData](
            data=EchoData(message="hello"),
            provenance=Provenance(
                library="mock-fixture", library_version="0.1.0", deterministic=True
            ),
        ),
        "Echo fixture completed.",
    )
    payload = json.dumps(result.model_dump(mode="json", by_alias=True, exclude_none=True), indent=2)
    schema = ScientificResult[EchoData].model_json_schema()
    return (
        "<!-- GENERATED FILE - DO NOT EDIT. Run make contract-docs. -->\n"
        "# Scientific contract v1 executable example\n\n"
        "The mock may additionally emit SDK server information and trace metadata.\n\n"
        f"```json\n{payload}\n```\n\n"
        f"Top-level fields: {', '.join(schema['properties'])}. "
        f"Required: {', '.join(schema['required'])}.\n"
        "The full outputSchema is generated through tools/list; make tools lists the live tools.\n"
    )


if __name__ == "__main__":
    Path("docs/contracts/example-v1.md").write_text(document())
