# J.A.R.V.I.S. v0.1.25

## Fixes

- Explicitly type both `generatedImagesIndex()` fallback results as `{ png: string[]; svg: string[] }`. This prevents TypeScript from inferring `never[]` for the empty fallback arrays and fixes the reported `index.png.includes(imageReference.filename)` error.
- Remove the module-level Pillow import from `test_image_artifact_validation.py`.
- Generate valid PNG test fixtures using the Python standard library (`struct`, `zlib`, and CRC32), so backend test collection does not require Pillow.
- Run the poster-refinement subprocess integration test with the configured `IMAGEGEN_PYTHON` isolated environment when available. Developer/CI fallback uses the current interpreter only when Pillow is installed; otherwise the integration-only test is skipped.
- Increment frontend package and FastAPI versions to 0.1.25.

## Compatibility

No application runtime dependencies, AI models, or model files are added, removed, or downloaded. Pillow remains in the isolated image-generation environment where the poster renderer uses it; it is no longer required just to collect or run backend artifact-validation unit tests.
