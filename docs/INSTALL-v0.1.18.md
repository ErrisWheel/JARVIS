# Install J.A.R.V.I.S. v0.1.18

1. Stop the running JARVIS backend and frontend terminals with `Ctrl+C`.
2. Extract the patch ZIP to `F:\JARVIS\patches\v0.1.18`.
3. Open PowerShell 5.1 in `F:\JARVIS\patches\v0.1.18` and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Apply-JARVIS-v0.1.18.ps1
```

The installer backs up each file it replaces to a timestamped folder under `F:\JARVIS\backups`, then copies the source overlay into `F:\JARVIS`.

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

No model downloads are needed. The patch does not touch the local model directories, Python environment, Node dependencies, or SQLite data.
