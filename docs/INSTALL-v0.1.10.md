# Install J.A.R.V.I.S. v0.1.10

This is an overlay patch for an existing J.A.R.V.I.S. v0.1.9 installation.

1. Stop the current backend and frontend PowerShell windows with `Ctrl+C`.
2. Extract the ZIP into `F:\` so its `JARVIS` folder merges into `F:\JARVIS`. Do not extract it inside `F:\JARVIS`.
3. In VS Code PowerShell at `F:\JARVIS\backend`, run:

   ```powershell
   ..\environments\python\Scripts\python.exe -m pytest .\tests -q
   ```

4. In VS Code PowerShell at `F:\JARVIS\frontend`, run:

   ```powershell
   npm run build
   ```

5. In VS Code PowerShell at `F:\JARVIS`, restart:

   ```powershell
   .\scripts\Start-JARVIS.ps1
   ```

## What to check

- Select the intended microphone in the Assistant panel and start Conversation Mode.
- Speak normally and watch **LIVE MIC LEVEL**. The number and bar should move. The orange marker is the speech gate only in Conversation mode; it is hidden in wake-word mode.
- The label should identify the active input device and whether the sound level is above the VAD gate. If the meter stays near 0%, verify the selected input in SteelSeries GG and Windows Sound settings.
- Submit a question. The chat no longer adds the generic "JARVIS is processing locally" filler; the hologram nodes show the real input, context, model and answer stages.
- After an answer, click a hologram node to inspect its stage, then select **HOW DID I REACH THIS ANSWER?** for an optional local explanation.

The explanation is a concise user-facing rationale generated locally from the request, answer, recent local conversation context and relevant saved-memory excerpts. It is not private token-by-token chain-of-thought. No cloud request is made.
