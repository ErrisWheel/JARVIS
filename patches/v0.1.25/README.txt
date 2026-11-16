JARVIS v0.1.25 INSTALLER HOTFIX (Windows PowerShell 5.1)

This hotfix replaces only Apply-JARVIS-v0.1.25.ps1. It corrects the
installer's package-lock.json validation for npm's valid empty root-package
key. The original package-lock.json is still copied unchanged.

Extract this ZIP into the already extracted folder:
F:\JARVIS\patches\v0.1.25
Choose overwrite/replace when prompted. This preserves the JARVIS overlay
already extracted by the original v0.1.25 ZIP.

Then run from PowerShell 5.1, working directory F:\JARVIS\patches:

  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
  & '.\v0.1.25\Apply-JARVIS-v0.1.25.ps1'

The installer validates all files before modifying the project and backs up
replaced files under F:\JARVIS\backups.
