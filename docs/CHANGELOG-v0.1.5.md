# J.A.R.V.I.S. v0.1.5 — Natural Voice and Adaptive Conversation

- Tightened the assistant persona for crisp, natural conversational replies, with one-to-three-sentence defaults for ordinary questions and more detail when requested.
- Added a dedicated voice-response prompt so spoken replies use natural sentences and avoid tables, Markdown bullets, and reading fenced code aloud.
- Kept Ollama token streaming; local speech begins at sentence boundaries rather than waiting for the complete answer.
- Fixed voice turn-taking so the post-response microphone follow-up window opens only after the model has finished generating and the complete speech queue has finished.
- Added code-aware speech segmentation so punctuation inside fenced and inline code is not treated as sentence boundaries.
- Expanded aggregate style adaptation with explicit feedback cues for casual/formal tone, brevity, detail, humor, and informal-language tolerance. The style profile still stores derived aggregate signals rather than raw message examples.
- Existing chat history remains stored locally in SQLite, and style learning remains user-toggleable.
- All inference, transcription, wake-word detection, and speech synthesis remain local. No paid services, cloud speech APIs, new runtime packages, or new model downloads are introduced.
- The spoken voice remains an installed local Windows/browser voice, not a cloned actor voice.
