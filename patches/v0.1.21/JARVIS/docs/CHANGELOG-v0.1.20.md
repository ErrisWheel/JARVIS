# J.A.R.V.I.S. v0.1.20

## Educational element posters: content and visual correction

- Added a curated, offline reference dataset for the ten requested elements: Cl, I, Br, He, Yb, F, At, Md, No and Ts.
- Poster facts are assembled deterministically when the operator explicitly supplies an `elements:` or `symbols:` list. The local chat model is no longer asked to invent discovery dates from a prompt containing symbols only.
- Discovery entries are sorted earliest-to-latest and distinguish first production/observation from conclusive synthesis. Nobelium is explicitly marked as a disputed discovery history.
- Each card includes atomic number, symbol, element name, date/milestone, discoverer/team, discovery method/context, and current periodic-table grouping and period.
- Added element-specific vector illustrations (flasks, crystals, solar spectrum, mineral sample, electrolysis cell, nuclear/accelerator motifs) plus category chips summarizing halogens, noble gas, lanthanoid and actinoids.
- Added source notes to the poster output and tests requiring non-empty content and visual metadata.
- Added contextual poster-refinement detection for follow-ups such as `make it detailed with some description and visuals`. It preserves the original operator-provided poster request and element list rather than trusting assistant-generated claims or losing the subject in context truncation.
- Generic educational poster extraction now asks the local model to use its offline knowledge for explanations and rejects empty detail fields rather than silently drawing blank cards.

## Compatibility

- No new model downloads, network access, cloud inference or dependency installation.
- Uses the existing Pillow-based local poster renderer; poster rendering does not load SDXL or CUDA.
- Generated poster PNGs remain under `F:\JARVIS\generated\images`.
