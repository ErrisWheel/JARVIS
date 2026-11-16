# J.A.R.V.I.S. v0.1.6 — Local Neural Voice

- Replaced browser/Windows `speechSynthesis` voices with a packaged local Kokoro-82M ONNX speech engine.
- Added an authenticated loopback-only `/api/tts/synthesize` endpoint that returns WAV audio generated in-process; model loading is lazy and the model is pre-warmed in the background when installed.
- Added four selectable English voice presets: George (British male, default), Lewis (British male), Michael (American male), and Adam (American male).
- Added local voice preview playback, voice selection persistence in browser-local settings, and STOP TALKING cancellation for playback and an in-flight speech request.
- The frontend synthesizes the next sentence while the current audio segment plays to reduce inter-sentence silence.
- Added a one-time, explicit-consent installer for the Kokoro package and model files. Pip cache, temporary files, and model files are directed to `F:\JARVIS`.
- Updated voice-mode prompting for calm, measured, articulate, natural spoken conversation, subtle wit, and fewer canned assistant phrases. This does not imitate a specific actor or clone a proprietary voice.
- Added tests for voice preset validation, text normalization, and local TTS installation reporting.
- Kokoro package/model are free and open-source (MIT package, Apache-2.0 model). All inference remains local after installation; no hosted TTS APIs or API tokens are used.
- English is the supported voice-language scope for this integration; Filipino/Taglish pronunciation may be imperfect.
