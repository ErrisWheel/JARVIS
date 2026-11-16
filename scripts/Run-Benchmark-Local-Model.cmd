@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Benchmark-Local-Model.ps1"
set "JARVIS_EXIT=%ERRORLEVEL%"
if not "%JARVIS_EXIT%"=="0" (
  echo.
  echo Benchmark exited with code %JARVIS_EXIT%.
  pause
)
exit /b %JARVIS_EXIT%
