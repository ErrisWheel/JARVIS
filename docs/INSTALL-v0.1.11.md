# Install J.A.R.V.I.S. v0.1.11

This is an overlay update for the existing v0.1.10 installation. Extract the patch ZIP into `F:\` so the `JARVIS` folder merges with `F:\JARVIS`. Do not extract it inside `F:\JARVIS`.

## 1. Apply the update

1. Stop the backend and frontend PowerShell windows with `Ctrl+C`.
2. Extract the patch into `F:\` and allow file replacement/merge.
3. Keep the original project folder; this is a patch, not a clean reinstall.

## 2. Install local image generation (optional)

Image generation is optional and stays unavailable until its separate environment and SDXL model are installed.

**Terminal:** VS Code integrated PowerShell  
**Directory:** `F:\JARVIS>`

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Install-Image-Generation.ps1
```

The installer:

- Requires Python 3.13 and at least 18 GB free on F:.
- Creates a separate image-generation environment at `F:\JARVIS\environments\imagegen`.
- Asks separately before installing local PyTorch CUDA 13.0 / Diffusers packages and before downloading the SDXL fp16 model (approximately 7 GB).
- Directs pip, Hugging Face, PyTorch, XDG, and temporary caches to `F:\JARVIS\cache`.
- Does not download models automatically at application runtime.

The selected model is `stabilityai/stable-diffusion-xl-base-1.0`. It can generate 1024×1024 images and can run as a standalone base pipeline. Its licence is CreativeML Open RAIL++-M, which has use restrictions; read the licence included in the model folder before using it. See the model card at Hugging Face.

After installation, JARVIS runs generation offline. It temporarily unloads active Ollama models to free GPU memory, starts an isolated worker, saves the PNG under `F:\JARVIS\generated\images`, then warms the default Ollama model again. Image generation may take noticeably longer than a text reply. Avoid gaming or other GPU-heavy work while it generates.

## 3. Use image generation

In Assistant, make an explicit visual request, for example:

- `Generate an image of a futuristic armored exosuit standing in a rainy city.`
- `Draw a detailed cutaway diagram of a fictional powered armor system.`
- `Visualize a holographic AI core with four interactive orbiting nodes.`

JARVIS routes these explicit requests to local SDXL. General questions such as “how does an exosuit work?” remain normal text questions.

## 4. Teach JARVIS how your codebase works

Open the **SELF DEV** tab. The local Coding Notebook lets you save project conventions, architecture rules, debugging lessons, and coding preferences. Only notes you explicitly save are retained. Those notes are supplied to local Qwen as context when generating future code proposals; they do not update the model weights.

Choose up to two source files from the safe allowlist and ask for one focused improvement. JARVIS creates a diff proposal; it does not apply it automatically. Review every diff and warning. Type the exact `APPLY:<proposal-id>` phrase to approve. A backup is made before the file is replaced. You can type `RESTORE:<proposal-id>` to roll back if the file has not changed since application.

The safe allowlist is intentionally narrow. It includes conversation-style rules, hologram visuals, CSS, and pure image-intent matching. Core API routes, authentication, filesystem/network policy, the main UI, voice listener, image worker, startup/install scripts, and self-development enforcement are protected.

There is no arbitrary command runner in this feature. JARVIS cannot run its own generated shell commands or approve a proposal itself. After applying code, you must manually test it.

## 5. Verify and start

**Terminal:** VS Code integrated PowerShell  
**Directory:** `F:\JARVIS\backend>`

```powershell
..\environments\python\Scripts\python.exe -m pytest .\tests -q
```

**Terminal:** VS Code integrated PowerShell  
**Directory:** `F:\JARVIS\frontend>`

```powershell
npm run build
```

**Terminal:** VS Code integrated PowerShell  
**Directory:** `F:\JARVIS>`

```powershell
.\scripts\Start-JARVIS.ps1
```

## 6. Privacy, cost and safety

- No paid API, hosted inference, subscription, per-image fee, or telemetry is used.
- The install script temporarily uses the internet only after you answer its download prompts. Runtime image generation is offline-only.
- Model downloads consume internet data and disk space; local generation uses electricity and GPU resources.
- The model is licensed, not public domain. CreativeML Open RAIL++-M restrictions apply.
- The self-development allowlist is an application-level guard, not a hard Windows security boundary. Because JARVIS runs under your normal Windows account, a compromised process could inherit that account's permissions. Do not treat this code review workflow as a replacement for OS isolation.
