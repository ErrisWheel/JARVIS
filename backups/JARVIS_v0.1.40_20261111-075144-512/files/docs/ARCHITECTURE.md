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
- **Default primary model:** `qwen3.5:9b`, configured in `backend/app/config.py`; the optional reviewer defaults to `qwen3:8b`. Model download size is not the same as runtime VRAM use. Evaluate context length, active GPU applications, and gaming behavior before changing model size.
- **Backend:** Python/FastAPI owns model calls, SQLite, telemetry, and policy checks. It binds to loopback only.
- **Frontend:** React + TypeScript + directly managed Three.js WebGL renderer. The existing Hologram component uses real 3D geometry, OrbitControls, raycasting, a procedural PMREM reflection environment, EffectComposer bloom, and backend activity state; no second React renderer root or demo app is introduced.
- **Storage:** all project-controlled paths are derived from the project root and point to F:. Runtime installs and Windows-owned files can still create small OS-managed entries outside F:.
- **Memory:** SQLite stores conversation turns and editable memories. An FTS5 external-content index with BM25 ranking stays synchronized through SQLite triggers. Retrieval is lexical, not embedding-based semantic/vector RAG.
- **Voice:** keep as a separate subsystem; do not use browser cloud speech APIs. Select local STT/TTS after hardware compatibility tests.
- **Permissions:** no shell-execution endpoint exists. No generic path endpoint exists. No internet-search endpoint exists. The import API accepts only operator-selected files stored in the dedicated imports folder. Document content is bounded and treated as untrusted reference material.
- **Resource policy:** GPU telemetry and a name-only allowlist of game processes determine Ollama placement/keep-alive settings. Under gaming or GPU pressure, Ollama receives `num_gpu: 0` when at least 8 GB host RAM remains. SDXL jobs are declined while a recognized game is active; CPU poster typesetting remains available.

## Security limits

Loopback binding, token checks, path validation, and the absence of shell execution reduce exposure, but do not constitute an OS-level sandbox. A compromised backend process running under your Windows account may still have the account's file permissions. A separate account or Windows sandbox would create a stronger boundary; you declined a separate account, so this starter does not claim hard isolation.
