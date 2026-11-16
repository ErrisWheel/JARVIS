# Image routing diagnosis — v0.1.42

The failure occurred before SDXL started. In v0.1.41, `extractContextualImageGenerationPrompt()` matched `diagram` as one of the structured poster kinds. That set `poster: true` in the image-generation request. The backend then called the local Ollama model and attempted to validate its response against `PosterContent`; the response failed the schema check, so the typography renderer stopped at the poster-structuring stage.

A direct visual request containing “diagram” already belongs to the general image-intent grammar, which routes to SDXL. v0.1.42 removes the conflicting poster classification and adds a server-side guard for clients that may still send the old flag.

## Verification

- Backend regression suite: 153 passed.
- Frontend image-intent and layout suites: 29 passed.
- Python application compilation: passed.
- Full Vite production build: not run in this source-only environment because `node_modules` is intentionally absent. Run `npm run build` on the Windows installation after applying the patch.
