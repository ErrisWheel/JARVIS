# J.A.R.V.I.S. v0.1.16 — Image Progress and Local Vision

## What changed

- SDXL worker emits structured `stage` and per-step `progress` events from Diffusers `callback_on_step_end`.
- The backend streams NDJSON while the worker is running, rather than waiting for a buffered `subprocess.run` result.
- ETA is calculated from measured recent denoising-step durations. It remains unavailable during model load/GPU preparation and is never fabricated; the final save/display stage is shown separately.
- Stopping the active response aborts the request; the backend terminates the worker before releasing the shared GPU lock, then cleans the request JSON.
- The backend verifies the final PNG signature and size before saving the image reference to conversation history or emitting `complete`.
- The frontend shows percentage, step count, total elapsed time, ETA, and final completion; the existing stop control cancels the stream.
- Generated image messages retain their filename through history restoration and include an `ASK JARVIS ABOUT THIS IMAGE` action.
- Follow-up questions that clearly refer to the latest generated image are routed to a local Ollama vision-language model. Only a validated 32-hex PNG filename under `generated/images` is accepted.
- Contextual poster requests such as `make a poster about it`, `make an infographic about these elements`, and the follow-through `generate using SDXL` use relevant recent conversation context and route to SDXL instead of ordinary text chat.
- Questions such as `why can't you import the images you created?` are recognized as image follow-ups and routed to the local vision analyzer when a recent generated image is available.

## Optional local image-understanding model

Image analysis is opt-in. No model is downloaded by the application.

The configured default is `qwen2.5vl:7b`, an Ollama vision model with image input and an approximately 6 GB download. To install it, explicitly approve the download:

```powershell
# VS Code PowerShell — directory: F:\JARVIS
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Install-Vision-Model.ps1
```

The installer refuses to pull the model if the configured `OLLAMA_MODELS` location is not `F:\JARVIS\ai\models\ollama`, unless the operator explicitly verifies the location when the variable is absent. It also checks F: free space and asks for `YES` before downloading.

After installation, restart JARVIS. Ask about the most recent generated image, or use the image's `ASK JARVIS ABOUT THIS IMAGE` button.

## Storage and privacy

- SDXL remains local and offline using the existing image environment and model.
- Vision analysis reads only a generated PNG under `F:\JARVIS\generated\images`.
- The image bytes are sent only to the local Ollama endpoint at `127.0.0.1:11434`; no hosted inference API is called.
- The vision model is unloaded after analysis and the default chat model is pre-warmed again to manage 16 GB VRAM.
- No new Python or npm dependency is added by this patch.

## Notes and limitations

- Model loading does not have a reliable ETA. The UI displays elapsed time and begins ETA only after measured denoising steps are available.
- The ETA is an estimate for remaining denoising steps and can change as step speed changes. Final PNG encoding and display follow the denoising stage and are shown as a separate finalization step.
- SDXL can still render small/complex text inaccurately. Contextual poster requests now reach SDXL, but exact scientific labels and typography require a deterministic text-layout compositor; this patch does not pretend SDXL is a reliable typesetter.
- The optional vision model must be installed before JARVIS can describe or critique generated images. Until then, the API returns an explicit installer instruction.
