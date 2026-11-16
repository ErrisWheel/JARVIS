# J.A.R.V.I.S. — Just A Rather Very Idiotic System

**Local-first personal AI workspace — Windows 11, VS Code, NVIDIA RTX 5080.**

Created by **Funduh (Erris)**. J.A.R.V.I.S. stands for **Just A Rather Very Idiotic System**.

This project is a local-first personal assistant foundation. It provides Ollama inference, SQLite conversation and memory storage, a Three.js hologram, live hardware telemetry, local Whisper transcription, an opt-in “Hey JARVIS” wake-word listener, streamed replies, local Kokoro neural speech, continuous microphone telemetry, on-demand answer-basis explanations, and aggregate conversational-style adaptation.

## Your hardware profile

- Windows 11 (user reports 26H2)
- AMD Ryzen 7 9800X3D
- ZOTAC GeForce RTX 5080 AMP Extreme Infinity — 16 GB VRAM
- 32 GB DDR5 (2 × 16 GB), currently configured at 6000 MT/s CL32
- JARVIS project/data target: `F:\JARVIS`
- Voice hardware target: KZ Castor Pro IEM + B800 microphone via SteelSeries GG

## What works in this bundle

1. **Local chat:** FastAPI talks to a local Ollama endpoint at `127.0.0.1:11434`. No cloud model is configured.
2. **Persistent history:** SQLite stores conversations on F:.
3. **Persistent memory manager:** Create, inspect, edit, search, and delete memory records in SQLite.
4. **Adaptive memory starter:** Direct English preference statements (for example, “I prefer concise answers”) are automatically captured. Uncertain, sensitive, or important operational knowledge is not automatically saved by this heuristic; add it after review. This is intentionally conservative and not yet semantic memory extraction.
5. **Learning modes:** Teaching, Interview, Practice, Review, and Correction modes change the local model's instructions. These are prompt/workflow modes, not model fine-tuning.
6. **Real 3D hologram:** Three.js / React Three Fiber, with mouse orbit/zoom and clickable Input, Context, Model and Answer nodes that report the live processing path.
7. **Actual system telemetry:** CPU/RAM from `psutil`; GPU/VRAM/temperature/power from `nvidia-smi` when available. No synthetic metrics.
8. **File boundary:** API exposes only the explicit `F:\JARVIS\imports` folder. There is no generic path read, shell execution, or file-system browsing endpoint.
9. **Loopback-only API:** Backend and frontend bind to `127.0.0.1`, not the LAN.
10. **Offline UI assets:** The dashboard uses system fonts; it does not fetch web fonts or remote assets.
11. **F: storage configuration:** Python venv, node_modules, npm cache, pip cache, model directory, database, logs, imports, and temporary files are directed to F:.
12. **Live microphone meter:** Shows the real input level from the selected sounddevice microphone, the voice gate in conversation mode, and the local transcription queue depth.
13. **Answer-basis explanation:** An optional local Ollama request summarizes the interpreted question, supplied context, saved-memory excerpts, high-level justification, and assumptions behind the latest answer. It is not a transcript of hidden chain-of-thought.

## What is NOT implemented yet

- Perfect speaker separation and acoustic echo cancellation. Continuous listening can still hear JARVIS's own speaker output; a headset and suitable microphone placement reduce false captures. The live meter helps verify the selected input level.
- Windows tray app and automatic Windows startup. Wake-word activation is available only while the dashboard is open and the user has explicitly enabled its microphone listener.
- True vector embeddings / semantic RAG / knowledge graph.
- Automatic GPU scheduling based on game detection. Hardware readings are real, but adaptive allocation is not yet wired in.
- Approved web-search and external-service tools. JARVIS makes no external requests in this starter.
- Fine-tuning. Saving memories does not train model weights.
- A hard OS-level security sandbox. Application path checks are not a security boundary against a compromised process running as your Windows user. Do not enable arbitrary code execution.

These are clearly tracked in `docs/ROADMAP.md`; they are not represented as completed features.

## Storage layout

Extract the ZIP so the project root is exactly `F:\JARVIS` (or extract then rename the folder to `JARVIS`). The setup script refuses to run from another drive.

```text
F:\JARVIS\
  backend\              FastAPI service
  frontend\             React + TypeScript + Three.js dashboard
  ai\models\            Ollama model storage target
  data\                  SQLite DB and local API token
  imports\               Only folder exposed for deliberate file imports
  logs\                  Application logs
  cache\                 pip/npm/temp caches
  downloads\             Installer/model helper downloads
  environments\          Python virtual environment
  runtime\               Optional local runtime install target
  scripts\               PowerShell setup/launch/model scripts
  docs\                  Architecture, security, roadmap
  .vscode\               VS Code tasks/settings
```

## Requirements

- Windows 11 x64
- Python 3.13 (64-bit) recommended; Python 3.12 is also accepted.
- Node.js 22.12+ (Node 22 LTS is the conservative choice for this Vite setup).
- VS Code
- NVIDIA driver that already detects the RTX 5080. Your reported 617.42 driver is above Ollama's documented NVIDIA minimum.
- Ollama for Windows, installed to `F:\JARVIS\runtime\ollama` where possible.

Ollama's Windows installer supports a custom directory (`/DIR=...`) and `OLLAMA_MODELS` can move model storage. If Ollama is already installed elsewhere, the helper moves its model storage but does not uninstall/move that existing binary; the script warns you. Its current GPU documentation lists RTX 5080 among supported NVIDIA cards. See `docs/REFERENCES.md`.

> **C: drive note:** JARVIS-managed files and caches are directed to F:. Windows itself, pre-existing Python/Node runtimes, NVIDIA drivers, and some installer/OS bookkeeping may still use Windows-managed locations. Your previously reported C: free space (3.43 GB) is critically low; free space before installing large dependencies.

## Installation — VS Code / PowerShell

1. Extract the ZIP to `F:\JARVIS`.
2. Open VS Code → **File → Open Folder** → `F:\JARVIS`.
3. Open **Terminal → New Terminal**. Confirm it is PowerShell.
4. Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\Setup-JARVIS.ps1
```

The setup script checks Python/Node, creates `F:\JARVIS\environments\python`, installs backend packages and frontend packages into F:, and creates local directories. It asks before downloading packages from the internet. It does **not** download a language model.

5. Install Ollama (only if not already installed):

```powershell
.\scripts\Install-Ollama.ps1
```

This script asks before accessing the internet, downloads the official Windows installer into `F:\JARVIS\downloads`, installs the application into `F:\JARVIS\runtime\ollama`, and configures the model directory at `F:\JARVIS\ai\models\ollama`.

6. Download the initial model only after approving its download:

```powershell
.\scripts\Pull-Model.ps1
```

Default model: `qwen3:8b` (about 5.2 GB in the Ollama library at the time this bundle was prepared). The RTX 5080's 16 GB VRAM is a sensible starting point for this quantized model, but real VRAM use also depends on context and other GPU applications. Close games while first validating inference.

7. Install local voice input and the opt-in Hey JARVIS wake-word detector (optional; asks separately before package/model downloads):

```powershell
.\scripts\Install-Voice-Model.ps1
```

8. Launch JARVIS:

```powershell
.\scripts\Start-JARVIS.ps1
```

The dashboard opens at `http://127.0.0.1:5173`. The backend listens only on `127.0.0.1:8787`.

To stop, close the two terminal windows opened by the launcher, or press `Ctrl+C` in each.

## First verification checklist

- Header reports Ollama reachable and model available.
- Send: `Hello, JARVIS. Identify yourself.`
- Confirm a real response comes from your local Ollama model.
- Open **Memory**, add a test memory, refresh the browser, edit it, then delete it.
- Open the hologram and drag/scroll to rotate/zoom it.
- Confirm CPU/RAM/GPU/VRAM show numbers or an explicit unavailable state.
- Confirm the database exists at `F:\JARVIS\data\jarvis.sqlite3`.
- Confirm model blobs are under `F:\JARVIS\ai\models\ollama`.
- Optional voice: choose the correct microphone in the Assistant panel, click **ENABLE HEY JARVIS**, say “Hey Jarvis”, pause briefly, then speak your request. After JARVIS answers, likely direct follow-ups can be spoken for about 17 seconds without repeating the wake phrase. The detector is an audio wake-phrase model, not a text search for the name JARVIS.

## VS Code shortcuts

- `Ctrl+Shift+P` → **Tasks: Run Task** → `JARVIS: Setup` / `JARVIS: Start` / `JARVIS: Backend tests`.
- Use the integrated PowerShell terminal for the scripts above.

## Troubleshooting

- `Ollama is unreachable`: launch the Ollama app or run `ollama serve` in a separate PowerShell terminal. Check `ollama list`.
- `No models installed`: run `.\scripts\Pull-Model.ps1` after confirming internet access.
- `nvidia-smi` unavailable: GPU panel reports telemetry unavailable; fix the NVIDIA driver installation before expecting GPU metrics.
- Port in use: close the conflicting local process; do not change the bind address to `0.0.0.0`.
- C: fills during setup: stop; do not continue installing. Move any remaining package caches/temp locations to F: and free Windows disk space first.

## Data and privacy

- No account, telemetry, cloud inference, remote API, internet search, or phone access is enabled.
- Ollama inference runs on the local machine.
- Package/model downloads happen only when you run a script and answer its confirmation prompt.
- Conversations and memories are local SQLite records under `F:\JARVIS\data`.
- JARVIS should only be given documents by placing them inside `F:\JARVIS\imports`. The starter does not recursively scan the rest of your drive.
- Do not store passwords, API keys, financial credentials, or other secrets as memories.

### Hey JARVIS hands-free voice mode

Run `scripts\\Install-Voice-Model.ps1` from `F:\\JARVIS` and approve package/model downloads individually. After restart, choose the Windows microphone in the Assistant panel and click **ENABLE HEY JARVIS**. Say “Hey Jarvis”, pause briefly, then speak. JARVIS uses local openWakeWord for the wake phrase, local Whisper for transcription, local Ollama for the answer, and the local Kokoro neural voice for spoken replies. Replies stream as the model generates them; JARVIS gives a brief acknowledgement and, if the first model output is delayed, one progress update for substantial tasks; short questions and conversational checks skip these fillers. Spoken clauses begin before the full answer is generated. After speaking, it accepts a likely direct follow-up for about 17 seconds without requiring another wake phrase, then returns to wake-word mode. A local phrase gate rejects obvious ordinary conversation, but this is not speaker recognition. The listener is opt-in and stops when disabled; it does not auto-enable at startup.


### Conversational style learning (v0.1.5)

The **LEARN MY STYLE** toggle is enabled by default because the operator requested adaptive conversational style. While enabled, JARVIS updates a local aggregate profile from successful user messages: approximate brevity, casual/formal tone, English/Filipino/Taglish mix, expressive punctuation, light-humor preference, and comfort with informal language. Explicit feedback such as “talk like me”, “keep it concise”, or “be witty” has priority over weak signals inferred from message length. The profile stores counts and derived signals, not raw message examples. The normal conversation database still stores chat history locally as before. Turn the toggle off at any time to stop updating and applying the profile. This does not fine-tune Qwen or change its model weights.

### Faster responses and local speech

Chat uses Ollama's streaming API so text appears as tokens arrive and speech begins at complete sentence boundaries. A response is not considered finished until both model generation and queued speech are complete, so the microphone does not reopen halfway through a spoken answer. Voice-mode prompts favor direct, natural spoken phrasing and avoid reading fenced code aloud. The selected local model is pre-warmed when the backend starts and is kept loaded for up to 15 minutes after use, trading some idle VRAM for lower first-token delay. Spoken replies use the selected local Kokoro neural voice. The wake listener pauses while JARVIS is speaking, then resumes in a short follow-up window so it does not hear its own voice. You can stop speech from the Assistant panel. The selected voice is a local neural preset, not a cloned actor or an exact copy of Siri.


## v0.1.6 — Natural local neural voice

J.A.R.V.I.S. can use the Kokoro-82M neural TTS engine locally instead of the generic browser voice. From a VS Code PowerShell terminal at `F:\JARVIS>`, install it with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Install-Neural-Voice.ps1
```

The installer asks before package installation and before the approximately 300 MB model/voice download. Model, pip cache, and temporary paths are directed to `F:\JARVIS`. After restarting, choose George (British male), Lewis (British male), Michael (American male), or Adam (American male) in the Assistant panel and click `TEST VOICE`. Since v0.1.8, Michael is the default to avoid the older-sounding George preset.

This is a neural voice, not an actor clone or exact Siri/JARVIS copy. It runs locally through ONNX Runtime; English is the supported voice-language scope, so Tagalog pronunciation may vary. See `voice/README.md` for details.

## Immediate voice responses (v0.1.7)

When **SPEAK REPLIES** is enabled, JARVIS requests a locally cached acknowledgement and starts Ollama generation concurrently. The acknowledgement is played first without delaying model generation. For substantial tasks only, if the first model output has not arrived 3.6 seconds after the request begins, JARVIS can play one brief progress update. Simple questions and check-in phrases skip both acknowledgement and progress audio. As text arrives, it is spoken in shorter sentence/clause chunks (with an approximately 68-character ceiling) rather than waiting for a complete long sentence. These are observable status updates, not private chain-of-thought narration. All audio is generated locally with Kokoro; no paid API is used.


## v0.1.8 voice update

Simple questions no longer trigger progress filler. Longer tasks can receive a short acknowledgement and a truthful progress update while Ollama generates concurrently. Default Kokoro voice is now Michael (`am_michael`) at 1.12x speed, with selectable voice and speech-rate settings. See `docs/INSTALL-v0.1.8.md`.


## v0.1.9 — Continuous conversation and live activity hologram

J.A.R.V.I.S. now offers an opt-in `CONVERSATION · NO WAKE PHRASE` mode. While enabled, a local microphone stream stays open and voice-activity detection segments speech. Local Whisper transcribes each utterance; a conservative local intent gate responds to direct questions, commands, explicit calls and follow-ups while ignoring ordinary statements and obvious friend-directed greetings. An explicit “Hey JARVIS” call takes priority even if the sentence begins by addressing a friend. The user can still choose the original `WAKE WORD · HEY JARVIS` mode. The microphone remains off until manually enabled.

Conversation Mode also supports barge-in: if the user starts speaking while J.A.R.V.I.S. is talking, the listener marks an interruption and the frontend cancels the current spoken/model response so the new request can take priority. Up to three utterances can wait in a small in-memory transcription queue while Whisper processes the previous utterance. Headphones/IEMs are recommended to reduce speaker-to-microphone echo.

The 3D hologram now has clickable Input, Memory, Model and Response nodes. Their inspector shows live application activity and context/retrieval summaries. It does not expose private hidden chain-of-thought.

Ignored nearby speech is transcribed locally only to classify whether it is a direct request, then discarded; its transcript is not saved to memory or written to logs. No new paid services or model downloads are introduced.

## v0.1.11 — Local image generation and supervised coding improvement

J.A.R.V.I.S. can generate images locally through Stable Diffusion XL Base 1.0. Image generation is optional: run `scripts\\Install-Image-Generation.ps1` from `F:\\JARVIS>` and approve the PyTorch/Diffusers installation and the approximately 7 GB fp16 model download separately. Model, Python environment, pip/Hugging Face cache, temporary files, and generated PNGs remain under `F:\\JARVIS`. Runtime inference is offline-only. Before generation, JARVIS attempts to unload active Ollama models to free VRAM; it cancels if an active model cannot be unloaded safely and warms the default model again after generation. The selected SDXL model is licensed under CreativeML Open RAIL++-M; read the licence and usage restrictions before using it. Full instructions: `docs/INSTALL-v0.1.11.md`.

The **SELF DEV** tab now includes a local Coding Notebook. Save your own project conventions, architecture notes, debugging lessons, and code preferences; future local Qwen code proposals receive those lessons as advisory context. This is persistent project knowledge, not model-weight training. JARVIS can propose changes only to a small allowlist of non-protocol feature files. It cannot edit the authentication/API boundary, filesystem/network policy, main UI, voice listener, image worker, startup scripts, or self-development enforcement. It cannot run arbitrary shell commands or approve its own proposals. Every code proposal must be reviewed and explicitly approved by the operator, creates backups, and has a rollback action. This is supervised feature editing, not an autonomous self-modifying agent or an OS-enforced sandbox.


## v0.1.12 — Natural image-request routing

Image generation now recognises conversational visual requests such as "show me a photo of...", "give me a picture of...", "can I see an image of...", "I want a photo of...", and common speech-recognition substitutions such as "did you let me a photo of...". It continues to leave ordinary questions about image generation as text conversations. The frontend checks `/api/images/status` at the moment of the request rather than relying on a possibly stale dashboard status, and reports whether the local runtime or SDXL model is missing. No new packages or models are required.

## v0.1.14 — Intelligence and instruction-following overhaul

This release replaces the previous fixed 512-token chat output ceiling with task-aware context/output budgets and automatic continuation for code tasks when Ollama reports a length stop. The per-conversation state stores a compact code anchor and last assistant output tail, so explicit requests such as “continue from here” are treated as continuations instead of a fresh file-generation request.

Operator corrections are stored in a dedicated SQLite table, separate from the inferred conversational style profile. Your previously stated “no emojis” and “no unsolicited jokes” corrections are seeded once when the database is upgraded; deleting either instruction in Memory management is respected on later restarts. Explicit instructions outrank style adaptation and persona.

Assistant messages containing fenced code blocks now include **DOWNLOAD CODE FILES**, which packages the code into a ZIP. The browser downloads it and a local copy remains in `F:\JARVIS\generated\exports`. The package includes a reminder to review code before running it. An explicit Stop control cancels the active response; short stop/cancel messages also stop instead of being sent back to the model.

Optional model candidates can be installed only after explicit approval with `scripts\Install-Reasoning-Models.ps1`. Run `scripts\Benchmark-Local-Model.ps1` to evaluate an installed model against a small local behavior suite. This benchmark is specific to JARVIS's instruction, continuation, complete-file and honesty regression cases; it is not an official general intelligence score. See `docs\INTELLIGENCE-AND-MODEL-STRATEGY.md` and `docs\INSTALL-v0.1.14.md`.
