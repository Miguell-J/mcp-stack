# Tool naming v1

Public names have a stable manifest namespace and machine-readable local name:
geometry.christoffel, mechanics.euler_poincare, variational.euler_lagrange,
symbolic.simplify. Human display_name never participates in routing.

The scientific policy is deliberately a subset of MCP's allowed characters:
lowercase ASCII letters, digits, underscores, hyphens and dots, beginning with a
letter in each namespace/local root, with a maximum full length of 128. Manifest
namespaces are unique even for disabled examples, preventing later activation
from silently introducing a collision.

Downstream `echo` under namespace demo becomes `demo.echo`. An already qualified
`demo.echo` remains `demo.echo`. The bridge strips that exact prefix before the
MCP One registry adds it, and the edge verifies the resulting name against the
preserved native Tool definition. `system.echo` under namespace demo becomes
`demo.system.echo`; use namespace system if the intended public name is system.echo.

If both echo and demo.echo occur in one downstream catalog, discovery rejects the
entire invalid catalog. Across servers, duplicate namespace manifests fail before
startup. Choose a different stable namespace or rename the conflicting local tool;
do not append random suffixes or numeric discovery-order counters. Every tool's
original native name remains available inside the bridge for SDK invocation.
