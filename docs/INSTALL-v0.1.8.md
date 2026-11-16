# Install J.A.R.V.I.S. v0.1.8

This is an overlay patch for the existing v0.1.7 project. Extract the archive into `F:\` so it merges into `F:\JARVIS`. Do not extract inside `F:\JARVIS`.

No new Python or Node packages and no model downloads are required.

## Verify backend

VS Code PowerShell, `F:\JARVIS\backend>`:

```powershell
..\environments\python\Scripts\python.exe -m pytest .\tests -q
```

## Build frontend

VS Code PowerShell, `F:\JARVIS\frontend>`:

```powershell
npm run build
```

## Restart

Stop the currently running backend and frontend with Ctrl+C. Then, VS Code PowerShell, `F:\JARVIS>`:

```powershell
.\scripts\Start-JARVIS.ps1
```

The existing `bm_george` selection is migrated to `am_michael` on first launch of this patch. Speech speed defaults to 1.12x. Both voice and rate remain selectable in the dashboard.
