# Installing J.A.R.V.I.S. v0.1.7

This is an overlay patch for an existing J.A.R.V.I.S. v0.1.6 installation. It adds immediate local speech acknowledgements and shorter streamed speech segments. It does not add packages or download another model.

## Apply the files

1. Stop the JARVIS backend and frontend with `Ctrl+C` in their respective PowerShell windows.
2. Extract the ZIP into `F:\` and allow it to merge with `F:\JARVIS`.
3. Do not extract the archive inside `F:\JARVIS`; that would create an unwanted nested `JARVIS` directory.

## Verify the backend

VS Code integrated PowerShell, working directory `F:\JARVIS\backend`:

```powershell
..\environments\python\Scripts\python.exe -m pytest .\tests -q
```

Expected result: `23 passed`.

## Verify the frontend

VS Code integrated PowerShell, working directory `F:\JARVIS\frontend`:

```powershell
npm run build
```

## Restart JARVIS

VS Code integrated PowerShell, working directory `F:\JARVIS`:

```powershell
.\scripts\Start-JARVIS.ps1
```

Ensure **SPEAK REPLIES** is enabled. With the neural voice installed, a spoken request should receive a short acknowledgement, followed by an optional progress phrase if the model has not started returning text after roughly 2.8 seconds. Generated answer speech begins in short sentence/clause chunks while the model is still generating.

All speech audio and inference stay local. These status phrases are user-facing progress cues, not private chain-of-thought narration.
