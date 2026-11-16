# J.A.R.V.I.S. v0.1.23 — Poster Refinement and Design Engine

## Fixed

- The frontend already exposed seven poster design names, but the PNG/SVG worker only implemented the original timeline/orbit alternatives. Unsupported families silently fell back to the older renderer. All seven families now route through the same real PNG/SVG design engine: cards, timeline, orbit, blueprint, museum, fieldnotes, and collage.
- New-layout selection is no longer a fixed sequential rotation. It fingerprints the new direction and recent design history, and avoids reusing one of the previous four layout families when alternatives are available.
- A redesign request starts a new composition while keeping the original educational content. Refinement requests retain the current composition family and apply the requested art direction, visual density, and decorative additions.
- Refinements load the actual prior PNG from `generated/images` after strict filename and directory checks. The worker samples low-detail edge areas and places new decorative elements there rather than claiming to have visually inspected an unavailable file.
- Structured poster content and the original source brief remain in the `.poster.json` sidecar, so later edits preserve facts and wording rather than asking the language model to reconstruct them on every turn.
- History restoration recognizes all seven design-family markers.

## New visual treatments

- **Cards:** compact two-column educational cards.
- **Timeline:** full-width chronological rail.
- **Orbit:** alternating panels around a center spine.
- **Blueprint:** technical grid, measurement marks, and schematic framing.
- **Museum:** framed exhibition cards and archival palette.
- **Fieldnotes:** paper, ruled notes, and notebook-style panels.
- **Collage:** asymmetric staggered panels with layered geometric accents.

Visual styles also include artsy, technical, vintage, museum, collage, watercolor, and minimal. High-visual-density requests add seeded decorative scientific motifs in available margins. PNG and editable SVG use the same selected design family and content.

## Local-only behavior

- No new models, network requests, cloud services, API subscriptions, or package dependencies.
- Poster typography and illustrations remain locally rendered. SDXL remains reserved for ordinary image-generation requests.
- Refinements only read files under JARVIS's own generated image directory.

## Validation

- Backend suite: 97 tests passed.
- Frontend image-intent suite: 13 tests passed.
- Seven poster design families each generated valid PNG and SVG files, and their PNG pixel outputs were distinct in the renderer regression test.
- Refinement test verified that the previous PNG is inspected and the output is regenerated.
- Python compilation passed.
- Full Vite production build was not run in the source-only validation environment because `node_modules` were not included.
