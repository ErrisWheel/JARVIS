$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
if ($Root -ne 'F:\JARVIS') { throw 'Run this script from F:\JARVIS.' }
$env:JARVIS_ROOT = $Root
$env:TEMP = Join-Path $Root 'cache\temp'; $env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $Root 'cache\pip'; $env:npm_config_cache = Join-Path $Root 'cache\npm'
$env:OLLAMA_MODELS = Join-Path $Root 'ai\models\ollama'; $env:OLLAMA_HOST = '127.0.0.1:11434'
$py = Join-Path $Root 'environments\python\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'Python environment is missing. Run .\scripts\Setup-JARVIS.ps1 first.' }
if (-not (Test-Path (Join-Path $Root 'frontend\node_modules'))) { throw 'Frontend packages are missing. Run setup first.' }
New-Item -ItemType Directory -Force -Path (Join-Path $Root 'data'),(Join-Path $Root 'logs') | Out-Null
# Backend binds only to loopback and writes all project-controlled state under F:\JARVIS.
$backendCmd = "`$env:JARVIS_ROOT='$Root'; `$env:TEMP='$($env:TEMP)'; `$env:TMP='$($env:TEMP)'; & '$py' -m uvicorn app.main:app --app-dir '$Root\backend' --host 127.0.0.1 --port 8787"
Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-Command',$backendCmd -WorkingDirectory $Root
$tokenFile = Join-Path $Root 'data\.api_token'
$ready = $false
for ($i=0; $i -lt 20; $i++) { Start-Sleep -Milliseconds 500; if (Test-Path $tokenFile) { try { Invoke-RestMethod 'http://127.0.0.1:8787/health' -TimeoutSec 1 | Out-Null; $ready = $true; break } catch {} } }
if (-not $ready) { Write-Warning 'Backend did not report healthy within 10 seconds. Check the backend terminal.' }
$frontendCmd = "`$env:JARVIS_ROOT='$Root'; `$env:TEMP='$($env:TEMP)'; `$env:TMP='$($env:TEMP)'; Set-Location '$Root\frontend'; npm run dev -- --host 127.0.0.1"
Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-Command',$frontendCmd -WorkingDirectory (Join-Path $Root 'frontend')
Start-Sleep -Seconds 2
Start-Process 'http://127.0.0.1:5173'
Write-Host 'JARVIS dashboard requested at http://127.0.0.1:5173' -ForegroundColor Cyan
Write-Host 'Two local PowerShell windows run the API and frontend. Close them or press Ctrl+C to stop.'
