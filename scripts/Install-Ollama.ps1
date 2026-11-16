$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
$env:TEMP = Join-Path $Root 'cache\temp'; $env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
if ($Root -ne 'F:\JARVIS') { throw 'Run this script from F:\JARVIS.' }
$models = Join-Path $Root 'ai\models\ollama'; New-Item -ItemType Directory -Force $models | Out-Null
$existing = Get-Command ollama -ErrorAction SilentlyContinue
if ($existing) {
  [Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $models, 'User')
  [Environment]::SetEnvironmentVariable('OLLAMA_HOST', '127.0.0.1:11434', 'User')
  Write-Host "Ollama already found: $($existing.Source)" -ForegroundColor Green
  if ($existing.Source -notlike 'F:\JARVIS\runtime\ollama*') { Write-Warning 'The existing Ollama application binary remains in its current location. Only its model storage is being moved to F:. To put the binary on F:, uninstall the existing copy in Windows Settings and rerun this script.' }
  Write-Host "Configured future Ollama launches to store models in $models. Quit and relaunch Ollama."
  exit 0
}
Write-Host 'This downloads the official Ollama Windows installer. The application will be installed under F:\JARVIS\runtime\ollama.' -ForegroundColor Yellow
$answer = Read-Host 'Allow internet access to download Ollama? (Y/N)'
if ($answer -notin @('Y','y','YES','yes')) { Write-Host 'Cancelled. No network request was made.'; exit 0 }
$downloads = Join-Path $Root 'downloads'; New-Item -ItemType Directory -Force $downloads | Out-Null
$installer = Join-Path $downloads 'OllamaSetup.exe'
Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $installer
$installDir = Join-Path $Root 'runtime\ollama'; New-Item -ItemType Directory -Force $installDir | Out-Null
Start-Process -FilePath $installer -ArgumentList "/DIR=`"$installDir`"" -Wait
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $models, 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_HOST', '127.0.0.1:11434', 'User')
$env:OLLAMA_MODELS = $models; $env:OLLAMA_HOST = '127.0.0.1:11434'
Write-Host 'Ollama installation finished. Quit and relaunch Ollama from the Start menu so it inherits the F: model path.' -ForegroundColor Green
Write-Host "Model location: $models"
