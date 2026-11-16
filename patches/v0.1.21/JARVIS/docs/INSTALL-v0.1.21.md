# Install v0.1.21

1. Stop both JARVIS terminals with Ctrl+C.
2. Extract the patch ZIP.
3. Run `Apply-JARVIS-v0.1.21.ps1` in PowerShell 5.1.
4. The installer backs up every replaced file under `F:\JARVIS\backups`.
5. Validate with `python -m pytest -q` in `F:\JARVIS\backend` and `npm run test:image-intent` / `npm run build` in `F:\JARVIS\frontend`.

No model download or dependency installation is required. Educational poster generation uses the local Ollama model for structured content and local Pillow/SVG rendering for readable text and visuals.
