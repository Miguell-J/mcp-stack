# ADR 0005: Audited upstream pin and operational image

Status: accepted, 2026-09-10.

Context: upstream HEAD 9e938ed fails compilation/import/test collection. Earlier
Phase 4 commit dafd1e1ed681a05f2dc7ea0c0e7ab796036c9689 compiles and retains
the required routing/circuit-breaker features. Packaging references a missing
README.rst and the Dockerfile cannot build as written. Two original tests fail
because of HTTP mocks. None of these findings justify a hidden source fork.

Decision: pin the full working commit in stack.yaml, keep a clean official clone
under .deps, use its original source directly inside an operational container
built by this repo with locked dependencies. Mount generated YAML at its existing
config path. No patches or copied upstream implementation are committed here.

Bootstrap refuses dirty/different checkouts; ref overrides are explicit. A future
versioned upstream image can replace the source build through mcp_one.image.
Runtime source and scientific adapters remain independently versioned.

Consequences: upstream tests are reported honestly; independent HTTP integration
tests validate runtime behavior. The native compatibility path works today while
upstream fixes are described, without expanding this task to modify MCP One/CRR.
