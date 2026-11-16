# J.A.R.V.I.S. v0.1.4 — Conversation and Voice

- Added NDJSON token streaming from local Ollama inference to the dashboard.
- Text appears progressively and local speech synthesis starts at sentence boundaries.
- The default model is pre-warmed at backend startup and kept resident for up to 15 minutes after inference.
- Added local conversational follow-up listening for up to 17 seconds after a spoken reply; another wake phrase is not required during that window. A conservative local phrase gate filters obvious ordinary conversation before sending a follow-up to chat; one ignored utterance closes the follow-up window and returns the detector to “Hey JARVIS” mode.
- The wake detector continues to require an audio match for “Hey Jarvis”; plain textual mentions do not activate the listener. When a detected wake phrase appears after a preamble, only the transcribed words following the final wake phrase are passed to chat.
- Added an opt-in/out aggregate conversational-style profile. It derives tone, brevity, language mix, expression, and light-humor patterns, and does not store raw message examples in the profile. Existing local chat history remains stored by the application.
- Tuned the assistant prompt for concise, confident, warm, subtly witty conversational replies.
- Added a stop-speaking control.
- No paid services, external inference, or new third-party Python/npm dependencies were added.
