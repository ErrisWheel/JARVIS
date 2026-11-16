# Architecture baseline

```text
Windows 11 user session
  └─ VS Code / browser (loopback only)
       └─ React + TypeScript + Three.js (127.0.0.1:5173)
            └─ Vite development proxy injects a local API token
                 └─ FastAPI (127.0.0.1:8787)
                      ├─ AI coordinator / learning-mode prompts
                      │    └─ Ollama API (127.0.0.1:11434)
                      ├─ Workspace + conversation + memory repository
                      │    ├─ SQLite (F:\JARVIS\data\jarvis.sqlite3)
                      │    ├─ FTS5/BM25 lexical index (always-available fallback)
                      │    └─ Optional local Ollama embeddings + same-workspace similarity graph
                      ├─ Operations layer
                      │    ├─ persisted activity events / hologram replay
                      │    ├─ supervised resumable task jobs
                      │    ├─ capability permission registry
                      │    ├─ declarative local skill manifests
                      │    └─ integrity-checked SQLite snapshots
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
- **Memory:** SQLite stores conversation turns, workspaces, and editable memories. An FTS5 external-content index with BM25 ranking remains the always-available fallback. Optional semantic retrieval uses an operator-selected, already-installed local Ollama embedding model; there is no automatic model download. Memory retrieval and vector relationships are scoped to the conversation's workspace.
- **Voice:** keep as a separate subsystem; do not use browser cloud speech APIs. Select local STT/TTS after hardware compatibility tests.
- **Permissions:** a persistent capability registry is checked at supported backend route boundaries. Arbitrary shell execution and external network access are hard-disabled. There is no generic arbitrary-path endpoint. The import API accepts only operator-selected files stored in the dedicated imports folder. Document content is bounded and treated as untrusted reference material. Declarative skill manifests are metadata only and cannot execute arbitrary code.
- **Resource policy:** GPU telemetry and a name-only allowlist of game processes determine Ollama placement/keep-alive settings. Under gaming or GPU pressure, Ollama receives `num_gpu: 0` when at least 8 GB host RAM remains. SDXL jobs are declined while a recognized game is active; CPU poster typesetting remains available.

## Security limits

Loopback binding, token checks, path validation, and the absence of shell execution reduce exposure, but do not constitute an OS-level sandbox. A compromised backend process running under your Windows account may still have the account's file permissions. A separate account or Windows sandbox would create a stronger boundary; you declined a separate account, so this starter does not claim hard isolation.


## Operations layer (v0.1.40)

- Workspaces own their conversations and memories. Legacy conversations migrate into the Personal workspace without changing the stored conversation messages.
- The operational timeline records backend facts such as request received, memory retrieval, model selection, task steps, image generation/analysis, and response completion/failure. It intentionally does not claim access to private model chain-of-thought.
- Task plans are constrained to approved local capabilities (local chat, memory retrieval, and imported-document search). Plans require an exact per-task approval phrase. Step results are persisted; interrupted tasks remain paused until the user reviews and explicitly resumes them.
- Backup snapshots use SQLite's online backup API, run integrity checks, and require explicit confirmation to restore.
- Voice remains based on the existing local Whisper/Kokoro and browser audio capture/playback paths. Browser echo-cancellation/noise-suppression constraints and barge-in are used where supported; a dedicated native acoustic echo-cancellation DSP pipeline is not included.
- Local image attachments are stored under the import boundary and are analyzed by the configured local vision model. The image-generation prompt no longer blanket-refuses a harmless image request solely because the subject is a real person; other safety restrictions still apply.
