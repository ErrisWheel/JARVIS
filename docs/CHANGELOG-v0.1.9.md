# J.A.R.V.I.S. v0.1.9 — Continuous Conversation and Interactive Activity Map

## Voice conversation
- Added opt-in **Conversation Mode** using continuous local voice-activity detection (VAD); no wake phrase is required.
- Retained optional **Hey JARVIS** wake-word-only mode.
- Local Whisper transcribes completed utterances; a conservative local intent gate routes direct questions, commands, explicit JARVIS calls and likely follow-ups.
- Obvious friend-directed greetings, reported speech, and ordinary statements/name mentions are ignored. An explicit “Hey JARVIS” call takes priority even when it follows a friend-directed opening. Ignored transcripts are not stored or written to logs.
- The microphone stream remains open during model generation and neural speech. When the user starts speaking over JARVIS, the listener emits a barge-in event; the current spoken reply and model generation are cancelled so the new request can take priority.
- Up to three complete utterances can wait in a small in-memory transcription queue while the listener keeps capturing; the queue is cleared when listening is stopped.
- Added a local speaking-state endpoint so the listener can distinguish ordinary listening from barge-in handling.

## Interactive hologram activity map
- Added selectable 3D nodes for Input, Memory, Model and Response.
- Added a live inspector panel with factual operational summaries sourced from the chat stream.
- The activity map reports context retrieval, active local model generation, streamed response and completion. It does not expose private chain-of-thought.

## Privacy and resource behavior
- Microphone stays off until the user explicitly enables Conversation Mode or Wake Word Mode.
- Audio is processed locally; ignored utterances are discarded after classification.
- No new external services, paid APIs or model downloads are introduced. Existing Whisper, microphone-capture and Kokoro installations are reused.
- Whisper transcribes one utterance at a time to avoid concurrent CPU-heavy jobs; up to three subsequent utterances can wait in memory while the microphone remains live.

## Validation
- Backend syntax compilation passed.
- Backend tests: 29 passed, including multiple queued utterances and explicit-call precedence after a friend-directed greeting.
- Full Vite/TypeScript production build was not run because frontend dependencies are not installed in the patch-building environment. Run `npm run build` on the target PC after applying the patch.
