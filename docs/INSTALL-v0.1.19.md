# Install J.A.R.V.I.S. v0.1.19

1. Stop the running JARVIS backend and frontend terminals with `Ctrl+C`.
2. Save the patch ZIP under `F:\JARVIS\patches\JARVIS_v0.1.19_Readable_Posters.zip`.
3. Open PowerShell 5.1 with working directory `F:\JARVIS\patches` and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Expand-Archive -LiteralPath 'F:\JARVIS\patches\JARVIS_v0.1.19_Readable_Posters.zip' -DestinationPath 'F:\JARVIS\patches\v0.1.19' -Force
Set-Location 'F:\JARVIS\patches\v0.1.19'
.\Apply-JARVIS-v0.1.19.ps1
```

The installer backs up each replaced file to a timestamped folder under `F:\JARVIS\backups`, then overlays the patch files. No model folders, SQLite databases, existing Python environments, or Node dependencies are replaced.

## Validate

PowerShell 5.1, working directory `F:\JARVIS\frontend`:

```powershell
npm run build
```

PowerShell 5.1, working directory `F:\JARVIS\backend`:

```powershell
& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q
```

## Start

PowerShell 5.1, working directory `F:\JARVIS`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Start-JARVIS.ps1
```

Contextual educational posters are now structured by the local lead model and rendered using actual font glyphs. They do not run SDXL. Ordinary image requests continue to use local SDXL as before.
