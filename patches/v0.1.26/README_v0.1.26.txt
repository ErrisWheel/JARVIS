J.A.R.V.I.S. v0.1.26 - LANDSCAPE AND INSTRUCTION ROUTING FIX

PURPOSE
- Enforce true landscape geometry for educational posters (1920 x 1080, 16:9).
- Persist orientation with generated poster history and restore it after reload.
- Verify actual PNG dimensions and SVG viewBox before reporting generation success.
- Route ordinary image requests (e.g. a realistic robot) to local SDXL even when
  the conversation contains an earlier poster.
- Keep arithmetic and ordinary text queries in the normal chat route.
- Recognize poster refinements, new compositions, orientation changes, and stop
  commands separately. A stop clears queued manual/voice messages.

FILES
- backend/app/main.py
- backend/app/imagegen_worker.py
- backend/app/poster_reference.py
- backend/tests/test_landscape_poster.py
- frontend/src/App.tsx
- frontend/src/api.ts
- frontend/src/imageIntent.ts
- frontend/tests/imageIntent.test.mjs
- frontend/package.json / package-lock.json (version metadata only)

INSTALL
Extract this archive to:
F:\JARVIS\patches\v0.1.26
Then run in Windows PowerShell 5.1, working directory F:\JARVIS\patches:

  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
  & '.\v0.1.26\Apply-JARVIS-v0.1.26.ps1'

The installer is PowerShell 5.1-compatible and deliberately does not use
ConvertFrom-Json on package-lock.json. It backs up every replaced source file
under F:\JARVIS\backups\pre-v0.1.26-<timestamp>.

VALIDATION PERFORMED IN THE PATCH BUILD ENVIRONMENT
- Backend: 107 tests passed.
- Frontend image-intent tests: 18 passed.
- Strict TypeScript check passed for api.ts and imageIntent.ts.
- App.tsx / api.ts / imageIntent.ts transpile syntax checks passed.
- Actual isolated worker CLI generated PNG + SVG at 1920 x 1080 in poster mode.
- PNG dimensions and SVG viewBox are checked against the requested canvas before
  either streaming or non-streaming endpoints return success.

LIMITATION
A full local `npm run build` was not run in the patch environment because this
source-only build does not contain frontend/node_modules. Run it in the installed
project after applying the patch.
