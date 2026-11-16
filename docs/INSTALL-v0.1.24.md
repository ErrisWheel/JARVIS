# Install J.A.R.V.I.S. v0.1.24

1. Stop both JARVIS terminal windows with `Ctrl+C`.
2. Save `JARVIS_v0.1.24_Poster_Refinement_And_Typescript_Fix.zip` to `F:\JARVIS\patches\`.
3. Extract the ZIP to `F:\JARVIS\patches\v0.1.24\`.
4. Open PowerShell 5.1 with the working directory `F:\JARVIS\patches` and run:

```powershell
New-Item -ItemType Directory -Force -Path '.\v0.1.24' | Out-Null
Expand-Archive -LiteralPath '.\JARVIS_v0.1.24_Poster_Refinement_And_Typescript_Fix.zip' -DestinationPath '.\v0.1.24' -Force
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& '.\v0.1.24\Apply-JARVIS-v0.1.24.ps1'
```

The installer backs up every replaced file beneath `F:\JARVIS\backups\pre-v0.1.24-<timestamp>`. It does not download models or install packages.

## Verify

Backend — PowerShell 5.1, working directory `F:\JARVIS\backend`:

```powershell
& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q
```

Frontend — PowerShell 5.1, working directory `F:\JARVIS\frontend`:

```powershell
npm run build
```

The backend tests now include a high-decoration SVG refinement regression. The frontend fallback is explicitly typed so `index.png.includes(imageReference.filename)` accepts a string.
