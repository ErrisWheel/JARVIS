# J.A.R.V.I.S. v0.1.43 installation

This is an incremental patch for an existing v0.1.42 installation. Stop both JARVIS terminals before installing. The patch changes frontend layout/routing, tests, release metadata and backend API version metadata only. It does not replace models, databases, imports, generated images, Python environments or `node_modules`.

Save `JARVIS_v0.1.43_Unified_Chat_Layout_Image_Followup_Fix.zip` to `F:\JARVIS\patches`, extract it to `F:\JARVIS\patches\v0.1.43`, then run `Apply-JARVIS-v0.1.43.ps1` in Windows PowerShell 5.1. The installer verifies payload hashes, creates a backup and rolls back changed files on verification failure.

After installation, from `F:\JARVIS\frontend`, run:

```powershell
npm run test:image-intent
npm run test:layout
npm run build
```

The trailing `svg` hint currently acts as a vector-style prompt hint; ordinary SDXL output remains a verified PNG. The exact editable SVG file export remains available through the existing typography poster renderer, not through the ordinary SDXL worker.
