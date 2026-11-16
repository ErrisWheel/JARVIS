# Install J.A.R.V.I.S. v0.1.20

1. Stop both JARVIS PowerShell windows with `Ctrl+C`.
2. Save the patch ZIP under `F:\JARVIS\patches\`.
3. Extract it and run `Apply-JARVIS-v0.1.20.ps1` from the extracted patch folder.
4. The installer creates a timestamped backup under `F:\JARVIS\backups` before replacing source files.
5. Run backend tests from `F:\JARVIS\backend`:

   ```powershell
   & 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q
   ```

6. Run the frontend production build from `F:\JARVIS\frontend`:

   ```powershell
   npm run build
   ```

7. Restart from `F:\JARVIS`:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   .\scripts\Start-JARVIS.ps1
   ```

No models, Python environments, Node dependencies, user database, or generated-image files are replaced by this patch.
