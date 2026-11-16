# J.A.R.V.I.S. v0.1.11 — Local image generation and supervised self-development

## Local image generation

- Added explicit local text-to-image routing for image, picture, illustration, photo, artwork, wallpaper, concept-art, diagram, visualisation, and render requests.
- Uses Stable Diffusion XL Base 1.0 through Diffusers in an isolated Python environment at `F:\JARVIS\environments\imagegen`.
- Model files are stored at `F:\JARVIS\ai\models\sdxl-base-1.0`; generated PNGs are stored at `F:\JARVIS\generated\images`.
- Runtime inference is offline-only. The worker enables Hugging Face and Transformers offline mode and loads only the local model directory.
- Before generation, JARVIS asks Ollama to unload active models to free GPU memory. If it cannot safely unload an active model, generation is cancelled rather than risking a VRAM conflict. JARVIS warms the default model again after the image worker exits.
- Image requests use fixed worker paths and a UUID-only output filename. The worker cannot receive a shell command or arbitrary output path.
- Image and request directories are checked for symbolic links and project-root containment.

## Supervised coding improvement

- Added a local coding-knowledge notebook at `F:\JARVIS\data\self_development\coding_knowledge.json`.
- Operator-authored lessons are included as advisory context in future local code proposals. They do not fine-tune Qwen or execute code.
- Expanded the safe editable source list to include the pure image-intent helper.
- Locked the frontend's main application, API client, Development Lab UI, backend API/security/configuration, voice listener, image worker, startup/install scripts, and self-development enforcement.
- Strengthened candidate validation against shell/process/network APIs, dynamic imports, common browser storage/network escape paths, Python builtins for file/dynamic-code access, and dunder attribute traversal.
- All proposals still require full diff review and exact operator confirmation. Applying creates backups; rollback requires a separate exact confirmation.

## Important limitations

- Image generation is unavailable until the operator runs the installer and approves both software/model downloads.
- SDXL Base 1.0 is licensed under CreativeML Open RAIL++-M. Read and comply with its licence and usage restrictions before use.
- Local image generation competes for GPU memory with other applications. JARVIS unloads active Ollama models, but the operator should close GPU-heavy games or tools during generation.
- Self-development is supervised source editing, not autonomous code execution, model-weight training, or an OS-enforced sandbox. The process still runs with the permissions of the logged-in Windows user.
- The code lab can edit only the explicit allowlist, at most two files per proposal. The operator must manually build and test changes after applying.
