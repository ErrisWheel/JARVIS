J.A.R.V.I.S. v0.1.18 SOURCE PATCH

1. Stop both JARVIS terminals with Ctrl+C.
2. Extract this ZIP to F:\JARVIS\patches\v0.1.18
3. In PowerShell 5.1, with working directory F:\JARVIS\patches\v0.1.18, run:

   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   .\Apply-JARVIS-v0.1.18.ps1

The installer backs up existing files to F:\JARVIS\backups before copying the overlay.
No model/runtime/environment/user-data directories are included in this ZIP.
See JARVIS\docs\INSTALL-v0.1.18.md for validation and startup commands.
