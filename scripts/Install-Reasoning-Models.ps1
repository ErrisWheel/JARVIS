$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
if ($Root -ne 'F:\JARVIS') { throw 'Run this script from F:\JARVIS.' }
$env:OLLAMA_MODELS = Join-Path $Root 'ai\models\ollama'
$env:TEMP = Join-Path $Root 'cache\temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:OLLAMA_MODELS,$env:TEMP | Out-Null
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw 'Ollama is not installed or not available in PATH.' }

Write-Host ''
Write-Host 'J.A.R.V.I.S. OPTIONAL LOCAL MODEL CANDIDATES' -ForegroundColor Cyan
Write-Host '1. qwen3.5:9b  - approx. 6.6–7.6 GB; good first candidate for general chat, coding and image input.'
Write-Host '2. gpt-oss:20b - approx. 14 GB; reasoning/tool-use candidate, but tight for a 16 GB GPU and may offload to system RAM.'
Write-Host '3. Both models'
Write-Host '4. Cancel'
$choice = Read-Host 'Choose 1, 2, 3 or 4'
$models = switch ($choice) {
  '1' { @('qwen3.5:9b') }
  '2' { @('gpt-oss:20b') }
  '3' { @('qwen3.5:9b','gpt-oss:20b') }
  default { @() }
}
if (-not $models.Count) { Write-Host 'No model downloaded.' -ForegroundColor Yellow; exit 0 }
Write-Host ''
Write-Host 'This next step requires internet access and downloads free open-weight model files to F:\JARVIS.' -ForegroundColor Yellow
Write-Host 'No paid API, account, subscription, or cloud inference is used.'
$approval = Read-Host 'Do you approve downloading the selected model(s)? Type YES'
if ($approval -cne 'YES') { Write-Host 'Download cancelled. No network request was made.' -ForegroundColor Yellow; exit 0 }
foreach ($model in $models) {
  Write-Host "`nPulling $model ..." -ForegroundColor Cyan
  & ollama pull $model
  if ($LASTEXITCODE -ne 0) { throw "Ollama failed to download $model (exit $LASTEXITCODE). No default model was changed." }
}
Write-Host ''
Write-Host 'Model download(s) completed. JARVIS will not change your selected model automatically.' -ForegroundColor Green
Write-Host 'Open the JARVIS dashboard and choose an installed model from LOCAL MODEL to test it.'
