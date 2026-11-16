# J.A.R.V.I.S. v0.1.13 — Image generation hotfix

This is a small overlay patch for an existing J.A.R.V.I.S. v0.1.12 installation. It does not reinstall SDXL, PyTorch, Diffusers, or any model files.

1. Stop the JARVIS backend with `Ctrl+C`.
2. Extract the patch ZIP into `F:\` and allow it to merge into `F:\JARVIS`.
3. In VS Code PowerShell at `F:\JARVIS\backend`, run:

   ```powershell
   ..\environments\python\Scripts\python.exe -m pytest .\tests -q
   ```

4. Restart JARVIS from `F:\JARVIS`:

   ```powershell
   .\scripts\Start-JARVIS.ps1
   ```

5. Try one image request. The worker should load SDXL, enable VAE slicing/tiling using the installed Diffusers API, and save the PNG under `F:\JARVIS\generated\images`.
