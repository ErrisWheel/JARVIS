@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Reasoning-Models.ps1"
set "JARVIS_EXIT=%ERRORLEVEL%"
if not "%JARVIS_EXIT%"=="0" (
  echo.
  echo Model installer exited with code %JARVIS_EXIT%.
  pause
)
exit /b %JARVIS_EXIT%
