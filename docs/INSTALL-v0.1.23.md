# Install J.A.R.V.I.S. v0.1.23

1. Stop both running JARVIS PowerShell terminals with `Ctrl+C`.
2. Save `JARVIS_v0.1.23_Poster_Refinement_Design_Engine_Fix.zip` under `F:\JARVIS\patches`.
3. Open PowerShell 5.1 with working directory `F:\JARVIS\patches`.
4. Extract the ZIP to `F:\JARVIS\patches\v0.1.23` and run `Apply-JARVIS-v0.1.23.ps1` from that directory.

The installer backs up every replaced file to `F:\JARVIS\backups\pre-v0.1.23-<timestamp>`. It changes source files only. It does not replace or download models, Python environments, Ollama, SDXL, or Node dependencies.

## Verify

Backend tests — PowerShell 5.1, working directory `F:\JARVIS\backend`:

```powershell
& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q
```

Frontend intent tests — PowerShell 5.1, working directory `F:\JARVIS\frontend`:

```powershell
npm run test:image-intent
```

Restart — PowerShell 5.1, working directory `F:\JARVIS`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Start-JARVIS.ps1
```

## Expected follow-up behavior

- `try something with more visuals`, `try something artsy`, and `put some design elements in the empty spaces` refine the latest poster, preserving its information and design family.
- `try generating a different design`, `start from scratch`, and `make a very different design with the same content` create a new composition, preserving the source material.
- A new PNG/SVG is returned only after the local worker has saved and verified both files.
