# Install J.A.R.V.I.S. v0.1.22

1. Stop both running J.A.R.V.I.S. PowerShell terminals with `Ctrl+C`.
2. Save the patch ZIP under `F:\JARVIS\patches`.
3. Extract the ZIP into `F:\JARVIS\patches\v0.1.22`.
4. In PowerShell 5.1, use `F:\JARVIS\patches` as the working directory.
5. Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& '.\v0.1.22\Apply-JARVIS-v0.1.22.ps1'
```

The installer backs up every replaced file under `F:\JARVIS\backups` and does not replace models, runtime binaries, Python environments, or Node dependencies.

After installation, run backend tests from `F:\JARVIS\backend`:

```powershell
& 'F:\JARVIS\environments\python\Scripts\python.exe' -m pytest -q
```

Run frontend image-intent tests from `F:\JARVIS\frontend`:

```powershell
npm run test:image-intent
```

Then restart from `F:\JARVIS`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Start-JARVIS.ps1
```
