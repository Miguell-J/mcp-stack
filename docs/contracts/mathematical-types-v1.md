# Mathematical types v1

These are serializable representations, not a CAS, tensor engine or unit library.

| Model | Representation |
| --- | --- |
| SymbolicExpression | expression + format; optional latex; symbols list |
| Scalar | finite number or symbolic expression |
| Vector | ordered components and optional matching basis |
| Matrix | two-dimensional shape and rectangular row-major component rows |
| Tensor | rank, shape, covariant/contravariant variance, dense/sparse representation, components |
| Equation | lhs, rhs, relation (eq/lt/le/gt/ge) |
| ArtifactReference | URI, media type, name; optional bytes, SHA-256 and description |

The format identifier is an adapter/library contract (for example sympy), not
permission to eval a string. LaTeX is presentation only. Symbols are explicit.
Complex numbers, manifold/chart identity, rich unit algebra and symbolic ASTs are
future typed extensions; do not invent incompatible encodings within v1.

Dense tensors use a flat row-major array whose length equals the shape product.
Sparse tensors use indexed components; omitted components are zero. Indices are
zero-based, unique and in bounds. Rank equals the length of shape and variance.
Rank-zero dense tensors have exactly one component. Inline components are capped
at 4096 and tensor rank at 12. Matrices validate rectangular shape; vectors validate
basis length. Numeric values reject nonfinite values and string/bool coercion.

Use ArtifactReference for datasets, trajectories and large arrays. The URI is an
opaque, explicit handle; no filesystem read or network fetch occurs during model
validation. The owner supplies a separate controlled resolver/resource service.
The mock demonstrates a small fixture resource and matching checksum; the edge
preserves its resource link but does not advertise resources/read federation yet.
