# J.A.R.V.I.S. v0.1.19

## Readable educational poster rendering

- Contextual poster requests now use the local lead Ollama model to convert the recent conversation/source material into validated poster data.
- Educational poster headings, element symbols, dates, and descriptions are rendered with real system-font glyphs using Pillow at 1536 × 2048. SDXL is no longer asked to draw the poster's text.
- The poster renderer uses a clean, high-contrast 2-column editorial layout for larger lists and a single-column layout for shorter lists.
- Poster composition runs in the existing isolated image-generation Python environment but does not load Diffusers, PyTorch, SDXL, or CUDA. It therefore does not compete with the local chat model for VRAM.
- The shared local-inference lock protects fact extraction from overlapping chat, vision, and image requests.
- Poster extraction uses only the supplied conversation/source material, preserves item names and symbols, and leaves unavailable dates/details blank rather than intentionally guessing. Chronological requests are sorted using stated dates.
- The image endpoint reports the actual 1536 × 2048 poster dimensions and distinguishes poster-renderer availability from SDXL availability.

## Carried-forward fixes

- Retains v0.1.18's directly managed Three.js hologram renderer, deleted-image history handling, expanded contextual conversation extraction, model-team status, and TTS request normalization/error reporting.
- Generic illustrations and other non-poster images continue to use the installed local SDXL model.

## Compatibility

- Uses the existing local Qwen3.5 9B lead model and existing image-generation Python environment.
- No model download, network access, cloud inference, or new dependency installation is required.
- All data and generated PNGs remain under the JARVIS project directory.
