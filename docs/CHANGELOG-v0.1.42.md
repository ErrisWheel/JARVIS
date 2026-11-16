# J.A.R.V.I.S. v0.1.42 — Image Routing Hotfix

## Fixed

- Generic diagram requests (for example, “generate me a diagram of wayang kulit puppet”) now route to ordinary local SDXL image generation instead of the structured educational-poster renderer.
- The contextual poster detector no longer treats the word `diagram` by itself as proof that the operator requested an educational poster.
- Explicit educational posters, infographics, timelines, charts and flyers retain the precise-typography renderer.
- Generic diagram parsing also supports “another diagram”, “the diagram” and “one diagram” phrasings.
- A backend defense-in-depth normalizer corrects stale clients that still send `poster: true` for a generic diagram, strips the old contextual-renderer wrapper where possible, and resets the image canvas to normal SDXL dimensions.
- Existing poster-related chat history does not hijack a new generic diagram request.

## Not changed

- No model, model weight, SDXL runtime, Python environment, Node dependency, database, user data or generated image is replaced.
- Explicit poster rendering and previous-poster refinement remain available.
