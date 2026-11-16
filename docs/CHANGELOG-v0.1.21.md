# J.A.R.V.I.S. v0.1.21 — Poster routing recovery

- Added an explicit full-brief educational poster detector. Long prompts with descriptive modifiers between the action verb and poster/infographic are routed to local poster mode.
- Preserves the complete operator brief up to 12,000 characters and raises backend/worker limits to match.
- Explicit poster prompts now set the `poster` request flag; previously only short contextual poster phrases did.
- Adds an editable, true-vector SVG companion for locally typeset posters, with real SVG text and vector illustrations. PNG remains the inline preview.
- Adds an SVG download button and a sandboxed local SVG API route.
- Expands the generic poster content schema with discoverer, location, institution, method, significance, classification, visual motif, takeaways and source note fields.
- Adds regression tests for the exact long-form prompt structure that previously fell through to text chat.

No models, runtimes, Python environments, Node modules or additional dependencies are downloaded.
