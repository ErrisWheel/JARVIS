# J.A.R.V.I.S. v0.1.24

## Fixed

- Fixed poster refinement failures where high-density decorative SVG artwork pushed the first editable `<text>` element beyond the first 2,048 characters. The backend now parses the complete SVG document and verifies its root, editable text, and vector/image artwork.
- Unified PNG/SVG artifact validation for both streaming and non-streaming image-generation endpoints.
- Improved generation failure diagnostics. When an artifact is missing or malformed, the API now reports which file failed validation and includes the worker exit status and available worker diagnostics.
- Fixed the frontend TypeScript `never[]` inference in generated-image history verification by explicitly typing the PNG/SVG index fallback. This resolves the reported `string is not assignable to never` error at `App.tsx`.

## Regression coverage

- Added an SVG fixture with over 2 KB of vector decoration before its first text node.
- Added malformed-SVG, textless-SVG, and PNG signature validation tests.
- Added an end-to-end subprocess-stream test for the exact refinement direction: `put artsy designs on blank parts`. It verifies that a new PNG and SVG are written and accepted by the backend.

## Compatibility

- No model downloads.
- No Python or Node dependency changes.
- No changes to the SDXL worker's model execution path.
- Existing poster manifests and generated files remain compatible.
