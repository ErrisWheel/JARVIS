# Installing J.A.R.V.I.S. v0.1.9

This is an overlay patch for the existing v0.1.8 project. It does not include models or `node_modules`.

1. Stop both J.A.R.V.I.S. backend and frontend terminals with `Ctrl+C`.
2. Extract the ZIP into `F:\` and allow it to merge into `F:\JARVIS`. Do not extract inside `F:\JARVIS`, or it will create a nested `JARVIS\JARVIS` folder.
3. Run backend tests in VS Code PowerShell from `F:\JARVIS\backend`:

   ```powershell
   ..\environments\python\Scripts\python.exe -m pytest .\tests -q
   ```

4. Build the frontend in VS Code PowerShell from `F:\JARVIS\frontend`:

   ```powershell
   npm run build
   ```

5. Start J.A.R.V.I.S. in VS Code PowerShell from `F:\JARVIS`:

   ```powershell
   .\scripts\Start-JARVIS.ps1
   ```

## Enable continuous conversation
- Select the intended microphone in the Assistant panel.
- Choose `CONVERSATION · NO WAKE PHRASE`.
- Click `START CONVERSATION`.
- Keep `SPEAK REPLIES` enabled for spoken answers.
- J.A.R.V.I.S. keeps the mic stream active and responds to clearly addressed questions or commands without requiring “Hey JARVIS”.
- Click `CONVERSATION ON` to stop listening and release the microphone.

`WAKE WORD · HEY JARVIS` remains available as an alternative. That mode still requires the existing wake-word model files. Continuous Conversation Mode only requires the already-installed local Whisper model and microphone dependencies.

## Behavior and limitations
- The local intent gate accepts common direct question and command forms and explicit JARVIS calls. It ignores ordinary statements, simple name mentions, clear friend-directed greetings and reported speech. An explicit “Hey JARVIS” call wins even when it follows a friend-directed opening in the same utterance.
- No microphone-only system can perfectly know whether an ambiguous question such as “What time is it?” was aimed at J.A.R.V.I.S. or another person. Conversation Mode treats recognizable direct questions/commands as intended for J.A.R.V.I.S.; turn it off when you want no assistant response.
- Use headphones/IEMs for reliable interruption detection. Speakers can leak J.A.R.V.I.S.'s own TTS back into the mic and cause false interruption detection.
- The activity hologram shows real application stages, context counts and model/response status—not the model's private hidden chain-of-thought.
- Ignored utterances are transcribed locally for classification, then discarded; their transcript text is not saved to memory or logged. Up to three complete utterances can wait in a small in-memory queue while Whisper processes the previous one.
