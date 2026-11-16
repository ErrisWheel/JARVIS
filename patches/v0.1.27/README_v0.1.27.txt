J.A.R.V.I.S. v0.1.27 — Conversation Restore Orientation Type Fix

Fixes the TypeScript build error at App.tsx:281 where API history allows
orientation=null but the frontend ChatLine type only permits a concrete
VisualOrientation or undefined.

The new normalizeOrientation(value: unknown) helper accepts only the two
supported values ('portrait' and 'landscape') and converts null/invalid
values to undefined. Both restoration assignments use the helper.

Installation (Windows PowerShell 5.1):
1. Stop both JARVIS terminals with Ctrl+C.
2. Save this ZIP as:
   F:\JARVIS\patches\JARVIS_v0.1.27_Orientation_Restore_Type_Fix.zip
3. Extract into:
   F:\JARVIS\patches\v0.1.27
4. Run from PowerShell 5.1:
   Set-Location F:\JARVIS\patches
   Expand-Archive -LiteralPath '.\JARVIS_v0.1.27_Orientation_Restore_Type_Fix.zip' -DestinationPath '.\v0.1.27' -Force
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   & '.\v0.1.27\Apply-JARVIS-v0.1.27.ps1'

The installer backs up only frontend\src\App.tsx under F:\JARVIS\backups.
It does not parse package-lock.json and does not install dependencies.

After installation, run:
  PowerShell 5.1, F:\JARVIS\frontend:
    npm run build

No model/runtime download is required.
