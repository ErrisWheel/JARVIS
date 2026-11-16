# JARVIS implementation roadmap

Status labels mean **implemented and locally testable**, **scaffolded**, or **not started**. A folder existing is not proof a feature works.

## Phase 1 — Discovery — COMPLETE

Hardware, OS, storage, voice hardware, development experience, network policy, file policy, startup behavior, display setup, personality, language, and intended roles recorded.

## Phase 2 — Architecture — BASELINE DOCUMENTED

- [x] Local model runtime boundary (Ollama on loopback)
- [x] Separate backend and frontend
- [x] SQLite persistence
- [x] Strict loopback binding and API token
- [x] Explicit import folder boundary
- [ ] Threat-model review and OS-level process isolation
- [ ] Architecture decision records for each later subsystem

## Phase 3 — Foundation — FIRST RUNNABLE SLICE

- [x] FastAPI backend
- [x] React/TypeScript frontend
- [x] Real Three.js hologram
- [x] Ollama chat integration
- [x] Persistent chat and memory CRUD
- [x] Actual hardware telemetry endpoints
- [x] VS Code tasks and PowerShell setup/launch scripts
- [ ] Automated packaging as signed Windows desktop app
- [ ] Tray process / hybrid startup integration

## Phase 4 — Intelligence — PARTIAL

- [x] Chat system personality and selectable learning-mode prompts
- [x] Conversation history
- [x] Manual memory CRUD
- [x] Conservative direct-preference capture heuristic
- [ ] Robust structured memory extraction with approval queue
- [ ] Embeddings and vector store
- [ ] Semantic RAG and source attribution
- [ ] Episodic/semantic memory separation and relationship graph
- [ ] Evaluation suite for recall, false memories, and corrections

## Phase 5 — Voice — PARTIAL

- [x] Local STT through faster-whisper on CPU (offline model)
- [x] Local spoken replies using Kokoro-82M neural TTS with selectable British/American voices
- [x] Opt-in local wake word “Hey Jarvis”
- [x] Microphone input selection from Windows audio devices (including SteelSeries virtual inputs)
- [x] Push-to-talk and opt-in wake-word listening with visible state; mic listener pauses during response speech
- [x] Local Kokoro neural speech playback and short post-response follow-up window
- [ ] Voice interruption / barge-in while JARVIS is speaking
- [ ] Dedicated TTS output-device selection
- [ ] Prosody/emotion controls and English/Filipino/Taglish pronunciation evaluation
- [ ] English, Filipino, and Taglish speech evaluation on the user's microphone

## Phase 6 — Holographic interface — FIRST VISUAL IMPLEMENTATION

- [x] Interactive 3D scene with orbit/zoom
- [x] State-reactive core and animated rings/particles
- [x] Dark cyan/blue/orange HUD design
- [ ] Audio-synchronized speaking visualization
- [ ] Listening / wake-word waveform fed by actual audio
- [ ] Responsive multi-monitor window management and portrait secondary view
- [ ] Accessibility and reduced-motion settings

## Phase 7 — Integration — PARTIAL

- [x] Frontend ↔ backend via local Vite proxy
- [x] Backend ↔ Ollama via localhost API
- [x] Backend ↔ SQLite
- [x] Backend ↔ hardware telemetry
- [ ] WebSockets and event bus
- [ ] Voice subsystem integration
- [ ] Desktop tray / startup manager

## Phase 8 — Testing and optimization — INITIAL TESTS ONLY

- [x] Backend import/compile check (bundle validation)
- [x] Unit tests for safe path and memory heuristic
- [ ] End-to-end test on the user's PC
- [ ] GPU offload verification during inference
- [ ] Performance and long-session memory tests
- [ ] Gaming resource pressure tests
- [ ] Security isolation / penetration tests

## Phase 9 — Advanced capabilities — NOT STARTED

- [ ] Permission-gated local tools
- [ ] Permission-gated internet research (approval for each request)
- [ ] Document parsers for deliberately imported files
- [ ] Task/reminder engine
- [ ] Approved script runner in a constrained sandbox
- [ ] Optional fine-tuning / LoRA experiments using separate datasets
- [ ] Phone companion over explicitly enabled, authenticated local network only

## Progress rule

Only mark a checkbox complete after the component has been implemented and tested. Memory storage is not model training. Prompt modes are not fine-tuning. GPU metrics are not neural activity.

- [x] Streamed local responses and sentence-level speech playback
- [x] Local follow-up conversation window after spoken replies
- [x] Aggregate conversational-style learning with explicit feedback cues and a user-facing toggle

- [x] Local neural Kokoro TTS with cancellable sentence-level playback and voice selection
