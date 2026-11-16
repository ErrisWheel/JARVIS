# J.A.R.V.I.S. v0.1.43

## Interface layout
- Consolidates Assistant, Intelligence Core, Memory, Operations, Self Development, and System Diagnostics into one persistent systems rail.
- Removes the permanently allocated center hologram column; the hologram remains available as a full workspace view.
- Makes Assistant the default primary workspace and lets it consume all remaining desktop width.
- Collapses the rail into a horizontally scrollable navigation strip on mobile; the selected workspace uses the available width.
- Keeps hardware summaries in the rail on desktop and exposes full diagnostics through the System view.
- Retains adjustable rail width, message composer sizing, reset-to-default, and all existing chat/voice/attachment handlers.

## Image generation routing
- Recognizes compound visual requests such as "generate me a diagram guide for a cutout puppet".
- Removes a trailing output hint such as `svg` from the prompt subject rather than passing it as artwork text.
- Recognizes follow-ups such as "turn that into an image" and builds a visual prompt from the immediately preceding operator request and JARVIS text/ASCII guide.
- Routes these requests directly into the existing local SDXL worker before normal chat, preventing the language model from answering with a text-only image refusal.
- Keeps explicit educational posters/infographics on the typography renderer.

## Validation
- Adds image-intent regression tests for compound diagram guides and contextual conversion from fenced ASCII instructions.
- Adds static workspace-layout regression checks for navigation structure, primary chat layout and mobile behavior.
- Full Vite production build and browser/device rendering still require verification on the operator's Windows installation.
