# Installing J.A.R.V.I.S. v0.1.25

1. Stop both running JARVIS terminals with `Ctrl+C`.
2. Extract the patch ZIP to a temporary folder under `F:\JARVIS\patches`.
3. Run `Apply-JARVIS-v0.1.25.ps1` from PowerShell 5.1.
4. From `F:\JARVIS\frontend`, run `npm run build`.
5. From `F:\JARVIS\backend`, run `& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q`.

The installer backs up every replaced file under `F:\JARVIS\backups`. It does not download packages or modify model files or Python environments.
