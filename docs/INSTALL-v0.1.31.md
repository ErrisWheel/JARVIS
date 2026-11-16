# J.A.R.V.I.S. v0.1.31 — Installation

## Before installing

1. Stop both JARVIS terminal windows with `Ctrl+C`.
2. Keep your existing `F:\JARVIS` project in place.
3. Save the integrated patch ZIP as `F:\JARVIS\patches\JARVIS_v0.1.31_Integrated_Upgrade.zip`.

The patch does not replace model files, SQLite databases, Python environments, Node modules, or user imports. The installer backs up each file it replaces under `F:\JARVIS\backups`.

## Apply (Windows PowerShell 5.1)

You may run this from any working directory:

```powershell
New-Item -ItemType Directory -Force 'F:\JARVIS\patches\v0.1.31' | Out-Null
Expand-Archive -LiteralPath 'F:\JARVIS\patches\JARVIS_v0.1.31_Integrated_Upgrade.zip' -DestinationPath 'F:\JARVIS\patches\v0.1.31' -Force
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& 'F:\JARVIS\patches\v0.1.31\Apply-JARVIS-v0.1.31.ps1'
```

The installer validates the staged SHA-256 manifest, checks the target root and destination paths for reparse points, creates rollback backups, installs the files, and verifies the installed hashes. It attempts rollback if an installation step fails.

## Verify the frontend

The visualization uses the Three.js dependencies already in the frontend package. No new frontend package installation is required. Run:

```powershell
Set-Location 'F:\JARVIS\frontend'
npm run build
```

## Verify the backend

```powershell
Set-Location 'F:\JARVIS\backend'
& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest tests -q
```

## Optional PDF support

DOCX, XLSX, and text/source imports do not require an extra package. PDF text extraction requires `pypdf`. It is optional; no package is downloaded by the patch installer. To add it, explicitly approve the package download and then run:

```powershell
& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pip install 'pypdf>=5.0,<7'
```

Scanned PDF OCR is not implemented.

## Start JARVIS

```powershell
Set-Location 'F:\JARVIS'
.\scripts\Start-JARVIS.ps1
```

## Important limitations

- Game detection uses a name allowlist; unrecognized games may not activate game-priority mode.
- CPU-only inference is selected only when at least 8 GB of available RAM is reported. If memory is below that threshold, the resource policy reports that CPU fallback is unsafe.
- Actual GPU scheduling, game performance, local model behavior, Windows-specific junction handling, and microphone/speaker routing require validation on the target PC.
- The path boundary is application-level protection, not an OS-enforced sandbox.
- Memory retrieval uses local SQLite FTS5/BM25 keyword ranking, not embedding-based semantic RAG.
- Voice gating is not acoustic echo cancellation.
