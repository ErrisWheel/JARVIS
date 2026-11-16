# J.A.R.V.I.S. v0.1.31 — Integrated upgrade

## Visualization

- Upgraded the existing `Hologram` component in place using its existing Three.js renderer; no separate demo or second React root was introduced.
- Added layered orbital geometry, procedural reflections, bloom post-processing, instanced memory markers based on the real memory count, and actual raycast selection/hover/camera focus.
- Animated pathways and pulses are driven by the backend's existing `input`, `memory`, `model`, and `response` activity states. No fabricated reasoning or tool events are displayed.
- Added camera reset/focus controls, resize handling, reduced-motion support, tab-visibility pausing, and resource-aware frame/pixel-ratio caps.

## Reliability and resource management

- Prevented dashboard refresh requests from overlapping; hidden tabs pause refreshes and partial status failures no longer block independent cards.
- Added a process-name allowlist game-priority policy. When a recognized game is active and at least 8 GB of available RAM is reported, Ollama requests are directed to CPU (`num_gpu: 0`) and model keep-alive is set to `0s`.
- GPU-heavy SDXL image generation is rejected while a recognized game is active; CPU typography/poster rendering remains available.
- Resource-policy state is surfaced in the diagnostics UI.

## Memory, files, and documents

- Added a SQLite FTS5 external-content index with BM25-ranked local memory retrieval and insert/update/delete synchronization triggers. A lexical fallback is used if FTS5 is unavailable; this is not vector/embedding semantic retrieval.
- Added deliberately selected local document import for bounded text/source files, DOCX, XLSX, and optional text-based PDF extraction through `pypdf`.
- Extracted content is bounded, cited with available line/paragraph/worksheet references, and passed to the model as untrusted reference material. Macros, scripts, and document-embedded instructions are not executed. Scanned PDF OCR is not included.
- Hardened managed import/data path resolution against traversal, symlink, and Windows junction escapes. This remains application-level defense, not an OS sandbox.

## Voice and lifecycle

- Added an adaptive voice activity gate while JARVIS is speaking and browser audio-output selection where supported. Existing barge-in behavior is retained.
- This is not acoustic echo cancellation; microphone/device-specific behavior still requires testing on the operator's PC.
- Replaced deprecated FastAPI startup hooks with a lifespan handler and orderly shutdown/cancellation.

## v0.1.30 audit fixes included

- SVG download validation examines the complete SVG rather than only its first 2 KB.
- API/frontend release versions are synchronized.
- First-run model pull defaults to `qwen3.5:9b`, matching backend configuration.
- Legacy image generation reports the actual requested image dimensions.
- Ollama endpoint configuration is restricted to loopback HTTP addresses.

## Validation

- Backend: 144 tests passed.
- Frontend image-intent tests: 19 passed.
- Python compileall: passed.
- TypeScript syntax transpilation: six source files checked with no syntax diagnostics.
- Full Vite production build was not run in the source-only build environment because `node_modules` is intentionally excluded and no dependency installation was performed.
- RTX 5080/Ollama/Windows PowerShell/audio hardware behavior must still be verified on the operator's PC.
