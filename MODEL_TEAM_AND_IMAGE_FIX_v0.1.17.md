# J.A.R.V.I.S. v0.1.17 — Model Team and Image Routing Fix

This is an overlay patch for an existing v0.1.16 installation. It does not download models or add package dependencies.

## Installed model roles

| Component | Role | When it runs |
|---|---|---|
| `qwen3.5:9b` | Lead conversational model | Produces the final response by default |
| `qwen3:8b` | Independent text reviewer | Reviews substantive requests before the lead model answers |
| `qwen2.5vl:7b` | Vision-language specialist | Inspects a generated PNG when the operator asks JARVIS to analyze it |
| SDXL | Image renderer | Generates requested images/posters |
| Whisper | Speech recognition | Transcribes local microphone/audio input |
| Kokoro | Neural speech output | Speaks the assistant's response locally |

The text reviewer is skipped for short acknowledgements/greetings. If the reviewer fails or is unavailable, the lead model continues without it. The selected text model remains the lead when it is installed; the other installed text model is selected as reviewer. Vision-only models are not offered in the text-primary dropdown.

## VRAM scheduling

The two text models do **not** stay loaded on the GPU simultaneously. Before a team pass, JARVIS unloads any prior Ollama sessions. The reviewer runs first with `keep_alive=0`, JARVIS verifies the reviewer session is released, and then the lead model generates the answer. Qwen2.5-VL and SDXL use the same exclusive local-inference scheduler. Chat, answer explanation, self-development proposals, vision analysis, and image generation are serialized around that scheduler so an image job cannot unload a model in the middle of a chat response. This is deliberate for the RTX 5080's 16 GB VRAM and avoids treating “all models” as “all model weights resident at once.”

The model team is local-only and uses the existing Ollama installation. No cloud calls, telemetry, paid services, model downloads, or new dependencies are introduced.

## Image-generation fixes

- Contextual poster/infographic/timeline commands now accept forms such as `can you create the poster now?`, `make theposter now`, and `make a poster about it`.
- Recent same-topic user and assistant turns are collected as source material. The prompt explicitly asks for an actual rendered image, not a text-only poster outline.
- Existing SDXL progress streaming and image worker are preserved.
- Missing historical image files are reported as expired/missing. JARVIS no longer tells the operator that an unavailable PNG is still saved, and does not offer vision analysis for an expired file.

SDXL is a diffusion image model; text-heavy posters can still contain imperfect typography. The prompt now prioritizes supplied symbols, dates, ordering, and legibility, but this patch does not claim perfect text rendering.

## TTS and React fixes

- The speech segmenter now hard-caps long unbroken strings as well as normal words, preventing an unusually long token from bypassing the 68-character segment target.
- API errors now format FastAPI/Pydantic validation arrays into readable field-level details. A persistent HTTP 422 should therefore show the rejected field or synthesis validation message, plus voice/speed/character-count diagnostics instead of `[object Object]`.
- Backend logs include the exact `ValueError` from Kokoro input validation.
- React StrictMode's development-only double mount has been removed from the dashboard entry point because the React Three Fiber Canvas owns an internal renderer root and can emit React 19 nested-root unmount warnings during StrictMode teardown/remount. App effects retain their explicit cleanup.

## Changed files

- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/model_team.py` (new)
- `backend/tests/test_model_team.py` (new)
- `backend/tests/test_intelligence_overhaul.py`
- `backend/tests/test_security_learning.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/imageIntent.ts`
- `frontend/src/main.tsx`
- `frontend/package.json`
- `frontend/package-lock.json`

## Validation performed for this patch

- Python compilation: passed.
- Backend test suite: **71 passed** (the pre-existing FastAPI `on_event` deprecation warning remains).
- TypeScript/TSX syntax transpilation: passed for `App.tsx`, `api.ts`, `imageIntent.ts`, and `main.tsx`.
- Contextual prompt checks: passed for `can you create the poster now?`, `make theposter now`, `now make a poster about it`, and an explicit infographic subject.
- A full Vite production build and live Ollama/RTX 5080 inference test were not run in this environment because the uploaded source snapshot does not include the installed frontend `node_modules` or the user's Windows runtime. The patch therefore still needs a local runtime check after installation.
