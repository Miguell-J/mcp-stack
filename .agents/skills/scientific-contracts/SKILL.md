---
name: scientific-contracts
description: Audit typed ScientificResult contracts, advertised schemas, provenance and scientific errors when adding or changing a scientific MCP adapter.
---

# scientific-contracts

Run from this repository root. Read [contract v1](../../../docs/contracts/scientific-result-v1.md).

1. Run `make test-contract test-template` against generated schemas and typed models.
2. Run `make test-integration test-e2e` using the clean pinned MCP One.
3. Validate every actual structuredContent against its advertised outputSchema. Also validate semantic cross-field constraints using the concrete ScientificResult[T] model: JSON Schema alone cannot enforce all dimensional relationships.
4. Cover omitted optional fields, malformed data, diagnostics, scientific error metadata and direct-versus-routed provenance/content equality.
5. Separate computational/structural validation from scientific interpretation. Preserve v1; do not introduce infrastructure imports into domain libraries.

Read [contract validation guidance](../../../docs/development-validation.md). Report exact tested models, commands and limitations.
