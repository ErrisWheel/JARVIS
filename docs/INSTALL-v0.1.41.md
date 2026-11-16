# Install J.A.R.V.I.S. v0.1.41

1. Stop both JARVIS terminal windows with `Ctrl+C`.
2. Extract the patch ZIP to `F:\JARVIS\patches\v0.1.41`.
3. In Windows PowerShell 5.1, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& 'F:\JARVIS\patches\v0.1.41\Apply-JARVIS-v0.1.41.ps1'
```

The cumulative installer accepts v0.1.29, v0.1.30, v0.1.31, v0.1.32, v0.1.40, and v0.1.41 (for repair/reinstallation). It verifies manifest SHA-256 hashes, rejects path traversal and junction/symlink destinations, backs up replaced files under `F:\JARVIS\backups`, verifies the installed release versions, and attempts rollback on failure. It does not install dependencies, download models, or replace data/models/environments.

Verify with Windows PowerShell 5.1 from `F:\JARVIS\frontend`:

```powershell
npm run build
npm run test:image-intent
npm run test:layout
```

Restart from `F:\JARVIS`:

```powershell
.\scripts\Start-JARVIS.ps1
```

## Controls
- Desktop: drag the thin vertical grips between the core-system rail / hologram and hologram / right rail.
- Tablet/mobile: drag the horizontal grip immediately above the right-hand chat/panel area to change its height.
- Any viewport: drag the small grip directly above the message field to resize the composer.
- Keyboard: focus a grip and use arrow keys; hold Shift for larger steps.
- Reset: top-bar circular-arrow button restores default sizes.

Layout preferences are stored in this browser profile under `jarvis-layout-sizes-v1`.
