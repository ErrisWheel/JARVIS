# J.A.R.V.I.S. v0.1.12 — Natural image-request routing

- Recognises natural visual requests: generate/create, show/give/get a photo or picture, can-I-see requests, and want/wanna-see phrasings.
- Handles the reported ASR transcript: `did you let me a photo of an Ironman suit?`.
- Allows short subjects such as `a cat` instead of rejecting them due to an unnecessarily high minimum prompt length.
- Keeps normal informational questions about images on the text-chat path.
- Checks the local image runtime/model availability immediately before calling SDXL, rather than trusting the periodically refreshed dashboard status.
- If image generation is unavailable, explains whether the isolated runtime or model download is missing instead of silently falling back to a text-only answer.
- No new packages, downloads, paid services, or external runtime calls.

## Validation

- Image intent parser compiled with TypeScript 5.8.3.
- 14 intent cases passed, including the exact reported transcript and negative cases for ordinary image-related questions.
- `imageIntent.ts`, `api.ts`, and `App.tsx` passed TypeScript transpilation syntax checks.
- Full merged backend suite: 42 passed.
- Full Vite build and real SDXL generation must still be run on the user's PC.
