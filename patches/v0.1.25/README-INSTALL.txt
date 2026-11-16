J.A.R.V.I.S. v0.1.25 — TypeScript and backend-test compatibility patch

Fixes:
- Explicit string[] typing at both generated-image index fallback declarations.
- Pillow-free backend test collection and PNG fixtures.
- Poster integration test uses the isolated F:\JARVIS\environments\imagegen\Scripts\python.exe when present.

Install:
1. Save this ZIP as F:\JARVIS\patches\JARVIS_v0.1.25_Typescript_And_Test_Environment_Fix.zip
2. Open PowerShell 5.1 with working directory F:\JARVIS\patches
3. Run:
   New-Item -ItemType Directory -Force -Path '.\v0.1.25' | Out-Null
   Expand-Archive -LiteralPath '.\JARVIS_v0.1.25_Typescript_And_Test_Environment_Fix.zip' -DestinationPath '.\v0.1.25' -Force
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   & '.\v0.1.25\Apply-JARVIS-v0.1.25.ps1'

Then validate:
- PowerShell 5.1, F:\JARVIS\frontend: npm run build
- PowerShell 5.1, F:\JARVIS\backend: & 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q

The patch creates a timestamped backup under F:\JARVIS\backups. No models or dependencies are downloaded.
