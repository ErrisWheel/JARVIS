# J.A.R.V.I.S. v0.1.15 — PowerShell and inline image display

This is an overlay patch for v0.1.14. Extract the `JARVIS` folder into `F:\` and merge it with the existing `F:\JARVIS` project. Do not extract inside `F:\JARVIS`.

## PowerShell script execution

The scripts are unsigned local project scripts. Do not permanently weaken the machine's execution policy. In a VS Code PowerShell terminal at `F:\JARVIS>`, use a process-only bypass:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Unblock-File .\scripts\Benchmark-Local-Model.ps1, .\scripts\Install-Reasoning-Models.ps1 -ErrorAction SilentlyContinue
& .\scripts\Benchmark-Local-Model.ps1
```

To install candidate reasoning models instead:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Unblock-File .\scripts\Install-Reasoning-Models.ps1 -ErrorAction SilentlyContinue
& .\scripts\Install-Reasoning-Models.ps1
```

Alternatively, run `scripts\Run-Benchmark-Local-Model.cmd` or `scripts\Run-Install-Reasoning-Models.cmd` from File Explorer. The wrappers launch PowerShell with a process-scoped `-ExecutionPolicy Bypass`; they do not change the permanent policy. If `Get-ExecutionPolicy -List` shows `MachinePolicy` or `UserPolicy` set to `AllSigned`, a Group Policy is controlling execution and local bypass may not work. Do not try to defeat that policy; ask the system administrator or use an approved signed copy.

## Inline generated images

The browser now retrieves generated PNGs with `fetch()` through the authenticated same-origin `/api/generated-images/{filename}` endpoint, then creates a local blob URL for the `<img>` element. This avoids relying on a native image request to carry the Vite proxy's injected API token. The code validates the random 32-hex PNG filename before requesting it and never fetches arbitrary model-provided URLs.

Previously saved assistant messages containing `[[JARVIS_IMAGE:<filename>.png]]` markers or same-machine JARVIS image links are hydrated into inline previews when conversation history loads. If a file is missing, JARVIS displays the expected local file path instead of pretending the image is visible.

No new Python or Node packages, model downloads, subscriptions, or external API services are required.

## Build and test

Backend tests:

```powershell
# VS Code PowerShell, F:\JARVIS\backend
..\environments\python\Scripts\python.exe -m pytest .\tests -q
```

Frontend production build:

```powershell
# VS Code PowerShell, F:\JARVIS\frontend
npm run build
```

Restart JARVIS from `F:\JARVIS>`:

```powershell
.\scripts\Start-JARVIS.ps1
```
