# Architecture baseline

```text
Windows 11 user session
  └─ VS Code / browser (loopback only)
       └─ React + TypeScript + Three.js (127.0.0.1:5173)
            └─ Vite development proxy injects a local API token
                 └─ FastAPI (127.0.0.1:8787)
                      ├─ AI coordinator / learning-mode prompts
                      │    └─ Ollama API (127.0.0.1:11434)
                      ├─ Memory + conversation repository
                      │    └─ SQLite (F:\JARVIS\data\jarvis.sqlite3)
                      ├─ Hardware monitor
                      │    ├─ psutil (CPU/RAM)
                      │    └─ nvidia-smi (GPU/VRAM/temp/power)
                      └─ Import boundary
                           └─ F:\JARVIS\imports only
```

## Decisions

- **Model runtime:** Ollama is used for native Windows GPU support and a simple local HTTP API. This avoids coupling the first implementation to a custom CUDA/PyTorch build. Your RTX 5080 is listed in current Ollama NVIDIA support documentation.
- **Initial model:** `qwen3:8b`, Q4_K_M, about 5.2 GB download. This is a practical initial fit for 16 GB VRAM. A 14B quantized model can be evaluated after measuring actual VRAM, context length, and gaming behavior.
- **Backend:** Python/FastAPI owns model calls, SQLite, telemetry, and policy checks. It binds to loopback only.
- **Frontend:** React + TypeScript + Three.js / React Three Fiber. The current 3D core is a real WebGL scene and responds to actual UI state.
- **Storage:** all project-controlled paths are derived from the project root and point to F:. Runtime installs and Windows-owned files can still create small OS-managed entries outside F:.
- **Memory:** first slice stores conversation turns and user-approved memories; a narrow heuristic catches explicit low-risk preference statements. Keyword retrieval is not vector RAG.
- **Voice:** keep as a separate subsystem; do not use browser cloud speech APIs. Select local STT/TTS after hardware compatibility tests.
- **Permissions:** no shell-execution endpoint exists. No generic path endpoint exists. No internet-search endpoint exists. The only import boundary is the dedicated imports folder.

## Security limits

Loopback binding, token checks, path validation, and the absence of shell execution reduce exposure, but do not constitute an OS-level sandbox. A compromised backend process running under your Windows account may still have the account's file permissions. A separate account or Windows sandbox would create a stronger boundary; you declined a separate account, so this starter does not claim hard isolation.
