# J.A.R.V.I.S. local voice system (v0.1.6)

The voice stack stays on this Windows PC:

- **Wake word:** openWakeWord listens for the audio phrase “Hey JARVIS”. It is opt-in and the mic is released when disabled.
- **Speech recognition:** faster-whisper transcribes the user's microphone audio locally.
- **Neural speech synthesis:** Kokoro-82M ONNX generates natural-sounding speech locally. The default preset is George (`bm_george`, British male); Lewis, Michael, and Adam are selectable in the dashboard.
- **Conversation:** Ollama generates the response locally. Text streams into the chat while Kokoro generates sentence-sized speech segments. One next segment is prepared while the current segment plays to reduce pauses.
- **Spoken style:** voice-mode instructions ask for calm, articulate, natural turn-taking and restrained wit. The TTS engine is not a clone of a film actor or an existing product voice.
- **Interrupt:** STOP TALKING cancels current playback and pending local speech generation.

## Install the neural voice

Open a VS Code PowerShell terminal at `F:\JARVIS>` and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\Install-Neural-Voice.ps1
```

The script separately asks permission to install the free Python package and to download the model and voice pack. The package is pinned to `kokoro-onnx==0.6.1`; the model files are stored in `F:\JARVIS\ai\models\kokoro`. The installer redirects pip cache and temporary files to the JARVIS folder on F:.

After installation, restart JARVIS and click **TEST VOICE** once in the dashboard. This helps confirm that the browser allows audio playback. Choose a voice preset from the adjacent selector. Since v0.1.8, Michael (`am_michael`, American male) is the default voice; George, Lewis and Adam remain selectable.

## Voice presets

| Preset | Voice | Accent |
|---|---|---|
| `bm_george` | George | British male |
| `bm_lewis` | Lewis | British male |
| `am_michael` | Michael | American male — default since v0.1.8 |
| `am_adam` | Adam | American male |

Kokoro's supported voice set and pronunciation are model-defined. English is the primary supported language in this JARVIS integration. Filipino/Taglish text can be synthesized, but pronunciation of Tagalog words may be inconsistent because this configuration uses English voice presets.

## Local-only guarantee

After the one-time approved package and model downloads, synthesis runs offline. The runtime does not call a hosted TTS API, does not require a key or account, and does not incur per-character or per-token charges. The open-source `kokoro-onnx` package is MIT-licensed and the Kokoro model is Apache-2.0-licensed.

The default implementation uses ONNX Runtime on the CPU to avoid CUDA/driver coupling and keep GPU resources available to Ollama and games. The audio is returned only to the local dashboard via the loopback API.

This is a neural voice, not guaranteed to match Siri's or any film character's exact voice quality. The selected voice preset, model generation speed, language, audio output device, room, and speakers/headphones all affect the result.


## Continuous conversation mode (v0.1.9)

The Assistant panel now supports `CONVERSATION · NO WAKE PHRASE`. When explicitly enabled, the backend keeps the selected microphone stream open and uses local voice activity detection to segment utterances. Whisper transcribes each utterance locally, and a conservative intent gate routes direct questions/commands or explicit calls to the assistant. Ordinary statements and obvious friend-directed greetings are ignored. An explicit “Hey JARVIS” call wins even when it appears after a social greeting in the same utterance.

`WAKE WORD · HEY JARVIS` remains available as a separate mode. Conversation Mode does not require the optional wake-word ONNX model, but it still needs the existing Whisper model and `sounddevice` dependency.

During neural speech playback the mic listener remains active. Starting to speak over JARVIS triggers a barge-in event, cancelling the current spoken output and model stream so the new request can take priority. Up to three complete utterances can wait in a small in-memory queue while local Whisper processes the prior one. Headphones or IEMs are recommended to minimize acoustic echo.

The local intent gate is heuristic, not speaker identification. Ambiguous direct questions may still be interpreted as requests while Conversation Mode is enabled. Turn Conversation Mode off when you do not want the assistant to respond.
