# Install J.A.R.V.I.S. v0.1.12

This is an overlay patch for your existing v0.1.11 installation. It adds no packages and does not download another model.

1. Stop the backend and frontend PowerShell windows with `Ctrl+C`.
2. Extract the ZIP into `F:\` so its `JARVIS` folder merges into `F:\JARVIS`. Do not extract it inside `F:\JARVIS`.
3. Build the frontend. In VS Code PowerShell at `PS F:\JARVIS\frontend>` run:

```powershell
npm run build
```

4. Test the backend. In VS Code PowerShell at `PS F:\JARVIS\backend>` run:

```powershell
..\environments\python\Scripts\python.exe -m pytest .\tests -q
```

5. Restart JARVIS. In VS Code PowerShell at `PS F:\JARVIS>` run:

```powershell
.\scripts\Start-JARVIS.ps1
```

## Try these image requests

- `Did you let me a photo of an Ironman suit?`
- `Can you show me a photo of an Iron Man suit?`
- `Give me a picture of a futuristic powered exoskeleton.`
- `I wanna see an image of a blue holographic AI core.`

The first request should now route to local SDXL, not to Qwen's text-only chat. If the dashboard reports that image generation is not ready, the application will now say whether the isolated image runtime or the SDXL model is missing. In that case, run `scripts\Install-Image-Generation.ps1` from `F:\JARVIS>` and approve the missing component's download.
