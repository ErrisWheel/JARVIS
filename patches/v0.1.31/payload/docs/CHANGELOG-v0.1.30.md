# J.A.R.V.I.S. v0.1.30 — Audit fixes

## Confirmed defects fixed
- The generated-SVG download route now uses the complete XML/artwork/text validator instead of inspecting only the first 2 KB.
- The legacy non-stream image endpoint now reports the exact canvas dimensions used for the render.
- FastAPI's reported version now matches the frontend release version.
- The first-run Ollama pull script and current setup documentation now match the configured `qwen3.5:9b` default; `qwen3:8b` remains the optional reviewer.
- Ollama URL configuration now rejects remote hosts, wildcard bind addresses, credentials, non-HTTP schemes, and unexpected URL paths so the backend cannot silently use remote inference.

## Regression coverage
- Large decorative SVG endpoint download.
- Legacy non-poster image dimensions.
- Backend/frontend version consistency.
- Local Ollama URL allowlist and remote URL rejection.

## Scope
- No new features or optional roadmap improvements implemented.
- No model files, databases, generated images, Python environments, or Node dependencies changed.
- No dependency versions changed.
