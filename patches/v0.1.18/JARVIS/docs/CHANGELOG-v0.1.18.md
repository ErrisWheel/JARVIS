# J.A.R.V.I.S. v0.1.18

## Fixes and changes

- Preserve the existing sequential multi-model pipeline: local text reviewer, lead model, vision specialist, and SDXL remain separate roles coordinated by the shared local-inference lock.
- Add a live model-team status strip to the dashboard showing lead, reviewer, vision, image-generation, and available local speech roles.
- Replace the React Three Fiber Canvas with a directly managed Three.js renderer. The hologram retains its 3D core, orbit controls, knowledge nodes, animated activity nodes, and clickable node selection without creating a nested React root.
- Annotate restored conversation image references with a server-side `image_available` flag. The frontend does not request deleted PNG files during history restoration, preventing repeated 404s.
- Use the recent conversation transcript as the context for poster follow-throughs instead of requiring a narrow set of element-related keywords.
- Expand poster intent matching for requests such as `can you create the poster now?`, `make theposter now`, `make a poster about it`, and `generate it using SDXL`.
- Normalize TTS voice/speed/text inputs, return actionable 400 errors for empty or oversized speech, and include the Kokoro rejection reason in the API response.
- Add regression tests for historical-image availability and TTS request normalization.

## Compatibility

- Uses the already installed Ollama models and SDXL/Kokoro/Whisper assets.
- Does not download models or install dependencies.
- Keeps model workloads serialized to protect a 16 GB GPU memory budget.
