$ErrorActionPreference = 'Stop'
$Root = 'F:\JARVIS'
if ((Get-Location).Path -ine 'F:\JARVIS') { throw "Extract the project to F:\JARVIS and run setup from that exact folder. Current folder: $((Get-Location).Path)" }
$Root = 'F:\JARVIS'
$env:JARVIS_ROOT = $Root
$env:TEMP = Join-Path $Root 'cache\temp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $Root 'cache\pip'
$env:npm_config_cache = Join-Path $Root 'cache\npm'
$env:HF_HOME = Join-Path $Root 'ai\cache\huggingface'
$env:OLLAMA_MODELS = Join-Path $Root 'ai\models\ollama'
$env:PYTHONDONTWRITEBYTECODE = '1'
@('backend','frontend','ai\models\ollama','ai\cache\huggingface','data','imports','logs','cache\temp','cache\pip','cache\npm','downloads','environments','runtime') | ForEach-Object { New-Item -ItemType Directory -Force -Path (Join-Path $Root $_) | Out-Null }

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
  $Python = 'py'; $PythonArgs = @('-3.13')
  & $Python @PythonArgs --version 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    $PythonArgs = @('-3.12')
    & $Python @PythonArgs --version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 (preferred) or 3.12 (64-bit), then rerun setup.' }
  }
} else {
  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCmd) { throw 'Python 3.13 or 3.12 (64-bit) is required. Install it, then rerun setup.' }
  $Python = 'python'; $PythonArgs = @()
  $detected = & $Python --version 2>&1
  if ($detected -notmatch 'Python 3\.(12|13)\.') { throw "Use Python 3.12 or 3.13. Detected: $detected" }
}
$pyVersion = & $Python @PythonArgs --version 2>&1
if ($LASTEXITCODE -ne 0) { throw "Python launcher failed: $pyVersion" }
Write-Host "Found $pyVersion" -ForegroundColor Cyan
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw 'Node.js 22.12+ is required. Install Node.js, then rerun setup.' }
$nodeVersion = node --version
Write-Host "Found Node $nodeVersion" -ForegroundColor Cyan

$venv = Join-Path $Root 'environments\python'
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { & $Python @PythonArgs -m venv $venv; if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python environment.' } }
$venvPython = Join-Path $venv 'Scripts\python.exe'
Write-Host 'This next step downloads Python packages and frontend dependencies from package registries.' -ForegroundColor Yellow
$answer = Read-Host 'Allow internet access for dependency installation now? (Y/N)'
if ($answer -notin @('Y','y','YES','yes')) { Write-Host 'Setup paused before downloads. You can rerun this script when you approve package downloads.' -ForegroundColor Yellow; exit 0 }
& $venvPython -m pip install --upgrade pip --cache-dir $env:PIP_CACHE_DIR
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $venvPython -m pip install -r (Join-Path $Root 'backend\requirements.txt') --cache-dir $env:PIP_CACHE_DIR
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Push-Location (Join-Path $Root 'frontend')
try { npm install --cache $env:npm_config_cache; if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' } }
finally { Pop-Location }
Write-Host ''
Write-Host 'JARVIS foundation dependencies installed.' -ForegroundColor Green
Write-Host "Python environment: $venv"
Write-Host "Project root: $Root"
Write-Host 'Next: .\scripts\Install-Ollama.ps1 (if required), then .\scripts\Pull-Model.ps1, then .\scripts\Start-JARVIS.ps1'
