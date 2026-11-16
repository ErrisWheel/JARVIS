# J.A.R.V.I.S. v0.1.22 — Poster Redesign and Image-History Recovery

## Fixed

- Recognize conversational poster redesign requests including “try generating a different design” and “start from scratch and create a different one”.
- Route those requests directly through the local poster-generation endpoint instead of normal chat.
- Keep the original operator brief separate from the generated redesign prompt so multiple redesigns preserve the same topic and facts.
- Rotate actual vector poster compositions between editorial cards, a full-width chronological rail, and an alternating orbital timeline.
- Validate alternate PNG and SVG renderers; reject invalid worker output before recording a completed image.
- Add an exact generated-image manifest and restore image/SVG metadata from conversation history.
- Do not request previews for model-invented filenames that do not exist in the local image archive.
- Prevent text-only model replies from claiming that an image was generated or saved when no verified image-service result exists.

## Validation

- 89 backend tests passed in the isolated test environment.
- 10 frontend image-intent tests passed.
- Python compilation passed for the backend entry point and image worker.
- Alternate timeline and orbit poster layouts each generated a 1536 × 2048 PNG and a valid SVG in the isolated test environment.
- Full Vite production build and live Windows/RTX inference were not run in the isolated environment.
