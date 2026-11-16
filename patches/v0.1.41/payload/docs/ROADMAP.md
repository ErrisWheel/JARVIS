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
- [ ] Threat-model review and OS-level process isolation (application-level path hardening exists; this is not OS isolation)
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
- [x] Optional local Ollama embeddings and cosine-similarity memory index (requires an already-installed embedding model selected by the operator; no model is downloaded automatically)
- [x] Workspace-scoped semantic retrieval and similarity graph, with SQLite FTS5/BM25 fallback when embeddings are unavailable
- [ ] Episodic/semantic memory separation and relationship graph with richer entity extraction (current graph connects actual memory vectors only)
- [ ] Evaluation suite for recall, false memories, and corrections

## Phase 5 — Voice — PARTIAL

- [x] Local STT through faster-whisper on CPU (offline model)
- [x] Local spoken replies using Kokoro-82M neural TTS with selectable British/American voices
- [x] Opt-in local wake word “Hey Jarvis”
- [x] Microphone input selection from Windows audio devices (including SteelSeries virtual inputs)
- [x] Push-to-talk and opt-in wake-word listening with visible state; mic listener pauses during response speech
- [x] Local Kokoro neural speech playback and short post-response follow-up window
- [x] Voice interruption / barge-in while JARVIS is speaking (existing conversation-mode path; acoustic echo cancellation remains unimplemented)
- [x] Browser TTS output-device selection where `setSinkId` is supported (system-default fallback otherwise)
- [ ] Prosody/emotion controls and English/Filipino/Taglish pronunciation evaluation
- [ ] English, Filipino, and Taglish speech evaluation on the user's microphone

## Phase 6 — Holographic interface — CINEMATIC THREE.JS UPGRADE

- [x] Interactive 3D scene with orbit/zoom and raycast node selection
- [x] State-reactive core, layered orbital geometry, instanced memory markers, animated event-driven neural pathways
- [x] Procedural environment reflections, EffectComposer bloom, camera focus transitions, reduced-motion and resource-aware frame caps
- [x] Dark cyan/blue/orange HUD design
- [ ] Audio-synchronized speaking visualization
- [ ] Listening / wake-word waveform fed by actual audio
- [ ] Responsive multi-monitor window management and portrait secondary view
- [ ] Accessibility and reduced-motion settings

## Phase 7 — Integration — LOCAL INTEGRATION COMPLETE

- [x] Frontend ↔ backend via local Vite proxy
- [x] Backend ↔ Ollama via localhost API
- [x] Backend ↔ SQLite
- [x] Backend ↔ hardware telemetry
- [x] Persisted backend activity-event timeline with selection/replay in the hologram (SSE remains the chat streaming transport; no WebSocket event bus)
- [x] Voice subsystem integration (existing local STT/TTS, cancellable speech, barge-in, and browser output routing)
- [ ] Desktop tray / startup manager

## Phase 8 — Testing and optimization — INITIAL TESTS ONLY

- [x] Backend import/compile check (bundle validation)
- [x] Unit tests for safe path and memory heuristic
- [ ] End-to-end test on the user's PC
- [ ] GPU offload verification during inference
- [ ] Performance and long-session memory tests
- [ ] Gaming resource pressure tests on the operator PC (unit policy tests pass; hardware verification remains outstanding)
- [ ] Security isolation / penetration tests

## Phase 9 — Advanced capabilities — PARTIAL

- [x] Backend-enforced permission manager for local chat, memory, imports, image generation/analysis, voice, and supervised code changes
- [ ] Permission-gated internet research (intentionally unavailable in this local-only build)
- [x] Local document parsers for deliberately imported files (text/source, DOCX, XLSX, optional pypdf for text PDFs; no OCR for scanned PDFs)
- [x] Supervised task planner with explicit approval, persisted step results, cancellation, and manual resume after interruption (no autonomous shell execution)
- [ ] Reminders and scheduled/background task engine
- [ ] Approved script runner in a constrained sandbox
- [x] Declarative local skill manifests (metadata and approved capability declarations only; arbitrary extension code is not executed)
- [x] Local SQLite backup snapshots with integrity-checked, explicitly confirmed restore
- [x] Workspace-scoped conversation history and memory, archive/restore, pin/rename/export/move workflows
- [x] Image attachments routed to the local vision model when the operator imports an image
- [x] Existing supervised self-development proposal/apply/rollback flow retained; changes require explicit approval
- [ ] Optional fine-tuning / LoRA experiments using separate datasets
- [ ] Phone companion over explicitly enabled, authenticated local network only

## Progress rule

Only mark a checkbox complete after the component has been implemented and tested. Memory storage is not model training. Prompt modes are not fine-tuning. GPU metrics are not neural activity.

- [x] Streamed local responses and sentence-level speech playback
- [x] Local follow-up conversation window after spoken replies
- [x] Aggregate conversational-style learning with explicit feedback cues and a user-facing toggle

- [x] Local neural Kokoro TTS with cancellable sentence-level playback and voice selection


## v0.1.31 update

- [x] Non-overlapping/visibility-aware dashboard refresh (unit/integration coverage in backend suite; browser soak test outstanding)
- [x] Local SQLite FTS5/BM25 memory retrieval with CRUD-synchronized index (lexical only; embeddings/semantic RAG remain planned)
- [x] CPU-only Ollama inference policy for recognized games or GPU pressure when host RAM reserve is adequate
- [x] Import-folder document extraction for text/source, DOCX, XLSX and optional PDF text parser
- [x] Browser output-device selector where supported; adaptive voice gate during TTS (not hardware AEC)
- [x] Three.js cinematic scene update in existing dashboard component
- [x] Event-driven neural activity timeline replayed from persisted backend events
- [ ] End-to-end Vite build and GPU/voice/browser validation on the operator's Windows PC


## v0.1.40 operations and intelligence update

- [x] Workspace management and conversation history actions (search, pin, rename, archive/restore, move, export)
- [x] Memory ownership and retrieval scoped to the active conversation workspace
- [x] Optional local embedding index and same-workspace similarity graph; BM25 remains the fallback
- [x] Persisted operational events and hologram replay from real backend events
- [x] Supervised local task planning, step-level persistence, cancellation, and manual recovery
- [x] Backend permission checks for supported local capabilities; shell and external network remain hard-disabled
- [x] Declarative skill registry with no arbitrary code execution
- [x] Integrity-checked SQLite snapshot and confirmed restore workflow
- [x] Local image attachments for vision analysis and deliberate document imports
- [x] Non-consensual/unsafe content restrictions retained while removing blanket refusals based only on a real person's identity
- [ ] Full Vite production build and device/GPU/voice validation on the operator's Windows PC
