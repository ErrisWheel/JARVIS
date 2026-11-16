J.A.R.V.I.S. v0.1.22 — Poster Redesign and Image-History Recovery

INSTALL
1. Stop both running JARVIS PowerShell terminals (Ctrl+C).
2. Save this ZIP to F:\JARVIS\patches\JARVIS_v0.1.22_Poster_Redesign_Recovery_Fix.zip.
3. In PowerShell 5.1, use F:\JARVIS\patches as the working directory.
4. Extract the ZIP into F:\JARVIS\patches\v0.1.22.
5. Run:

   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   & '.\v0.1.22\Apply-JARVIS-v0.1.22.ps1'

The installer creates a timestamped backup under F:\JARVIS\backups before replacing source files. It does not download or replace models, dependencies, runtimes, or environments. All patch files are source code, tests, and documentation.

After installing, run backend tests in F:\JARVIS\backend:
   & 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q

Run frontend image-routing tests in F:\JARVIS\frontend:
   npm run test:image-intent

Then restart from F:\JARVIS:
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   .\scripts\Start-JARVIS.ps1
