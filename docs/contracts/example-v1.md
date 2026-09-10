<!-- GENERATED FILE - DO NOT EDIT. Run make contract-docs. -->
# Scientific contract v1 executable example

The mock may additionally emit SDK server information and trace metadata.

```json
{
  "_meta": {
    "io.github.miguell-j.scientific/contract": {
      "family": "scientific-result",
      "version": 1
    }
  },
  "content": [
    {
      "type": "text",
      "text": "Echo fixture completed."
    }
  ],
  "structuredContent": {
    "data": {
      "message": "hello"
    },
    "provenance": {
      "library": "mock-fixture",
      "library_version": "0.1.0",
      "deterministic": true
    }
  },
  "isError": false,
  "resultType": "complete"
}
```

Top-level fields: data, context, diagnostics, provenance. Required: data.
The full outputSchema is generated through tools/list; make tools lists the live tools.
