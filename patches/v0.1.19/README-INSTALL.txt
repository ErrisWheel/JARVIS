J.A.R.V.I.S. v0.1.19 — READABLE EDUCATIONAL POSTERS

WHY THIS FIX EXISTS
SDXL is good at producing artwork, but it does not reliably draw exact words,
chemical symbols, dates, or dense explanatory text. This patch changes
contextual educational posters to use the local lead model to structure facts,
then Pillow and installed system fonts to typeset the finished 1536 x 2048 PNG.
Posters do not load SDXL, PyTorch, or CUDA. Ordinary image requests still use
local SDXL as before.

INSTALL
1. Stop the JARVIS backend and frontend terminals with Ctrl+C.
2. Save this ZIP as:
   F:\JARVIS\patches\JARVIS_v0.1.19_Readable_Posters.zip
3. Open PowerShell 5.1. Working directory: F:\JARVIS\patches
4. Run:

   New-Item -ItemType Directory -Force -Path 'F:\JARVIS\patches\v0.1.19' | Out-Null
   Expand-Archive -LiteralPath 'F:\JARVIS\patches\JARVIS_v0.1.19_Readable_Posters.zip' -DestinationPath 'F:\JARVIS\patches\v0.1.19' -Force
   Set-Location 'F:\JARVIS\patches\v0.1.19'
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   .\Apply-JARVIS-v0.1.19.ps1

The installer backs up replaced source files into a timestamped folder under
F:\JARVIS\backups before copying the patch. It does not replace model files,
Python environments, Node dependencies, databases, or generated images.

VALIDATE
PowerShell 5.1, working directory F:\JARVIS\backend:

   & 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q

PowerShell 5.1, working directory F:\JARVIS\frontend:

   npm run build

START
PowerShell 5.1, working directory F:\JARVIS:

   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   .\scripts\Start-JARVIS.ps1

NO NEW MODEL DOWNLOADS OR PAID SERVICES ARE REQUIRED.
