# Install J.A.R.V.I.S. v0.1.40

Stop JARVIS before updating. Save/extract the ZIP to `F:\JARVIS\patches\v0.1.40`. Open Windows PowerShell 5.1 and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& 'F:\JARVIS\patches\v0.1.40\Apply-JARVIS-v0.1.40.ps1'
```

Run `npm run build` and `npm run test:image-intent` from `F:\JARVIS\frontend`, then restart using `F:\JARVIS\scripts\Start-JARVIS.ps1` from the project root. See `INSTALL.txt` and `IMPLEMENTATION-REPORT-v0.1.40.md` for safeguards, tests and limitations.
