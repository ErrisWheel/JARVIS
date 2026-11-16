# Installing J.A.R.V.I.S. v0.1.14

This is an overlay patch for the existing J.A.R.V.I.S. installation. It is designed for `F:\JARVIS`.

1. Stop the running backend and frontend PowerShell windows with `Ctrl+C`.
2. Extract the patch ZIP into `F:\` so its `JARVIS` folder merges into `F:\JARVIS`. Do not extract inside `F:\JARVIS`.
3. Run backend tests in VS Code PowerShell from `F:\JARVIS\backend`:

   ```powershell
   ..\environments\python\Scripts\python.exe -m pytest .\tests -q
   ```

   Expected: `60 passed` (the test environment reports two existing FastAPI startup-event deprecation warnings).

4. Build the frontend in VS Code PowerShell from `F:\JARVIS\frontend`:

   ```powershell
   npm run build
   ```

5. Start J.A.R.V.I.S. in VS Code PowerShell from `F:\JARVIS`:

   ```powershell
   .\scripts\Start-JARVIS.ps1
   ```

## Optional stronger local model candidates

The current selected model is not changed by this patch. To review and optionally download Qwen3.5 9B or GPT-OSS 20B, run this in VS Code PowerShell from `F:\JARVIS`:

```powershell
.\scripts\Install-Reasoning-Models.ps1
```

Each model download requires explicit approval (`YES`). No download happens if cancelled. Model files are stored under `F:\JARVIS\ai\models\ollama`.

## Benchmark an installed model

Run this in VS Code PowerShell from `F:\JARVIS`:

```powershell
.\scripts\Benchmark-Local-Model.ps1
```

Enter the exact tag shown by `ollama list`. The small local regression report is written to `F:\JARVIS\reports\model_benchmarks`. It tests a handful of JARVIS-specific behaviors; it is not a general intelligence score.

## Code exports

When an assistant message contains complete fenced code blocks, use its **DOWNLOAD CODE FILES** button. A ZIP is downloaded by the browser and a local copy is stored in `F:\JARVIS\generated\exports`. Review generated code before running it.
