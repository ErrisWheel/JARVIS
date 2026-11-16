$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
if ($Root -ne 'F:\JARVIS') { throw 'Run this script from F:\JARVIS.' }
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) { throw 'Ollama CLI not found. Run .\scripts\Install-Ollama.ps1 first, then open a new PowerShell terminal.' }
$env:OLLAMA_MODELS = Join-Path $Root 'ai\models\ollama'
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $env:OLLAMA_MODELS, 'User')
Write-Host 'This will download qwen3:8b (approximately 5.2 GB) into F:\JARVIS\ai\models\ollama.' -ForegroundColor Yellow
$answer = Read-Host 'Allow internet access for this model download? (Y/N)'
if ($answer -notin @('Y','y','YES','yes')) { Write-Host 'Cancelled. No network request was made.'; exit 0 }
ollama pull qwen3:8b
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
Write-Host 'Model downloaded. Verify with: ollama list' -ForegroundColor Green
