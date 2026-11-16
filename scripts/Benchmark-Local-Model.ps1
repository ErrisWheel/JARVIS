$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
if ($Root -ne 'F:\JARVIS') { throw 'Run this script from F:\JARVIS.' }
$py = Join-Path $Root 'environments\python\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'JARVIS Python environment not found.' }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw 'Ollama is not available in PATH.' }
Write-Host 'Installed local models:' -ForegroundColor Cyan
ollama list
$model = Read-Host 'Enter the exact model tag to benchmark (example: qwen3:8b)'
if ([string]::IsNullOrWhiteSpace($model)) { throw 'A model tag is required.' }
& $py (Join-Path $Root 'scripts\Benchmark-Local-Models.py') --model $model
if ($LASTEXITCODE -ne 0) { Write-Warning 'The behavior benchmark reported failures. Review the JSON report; this is not a general intelligence score.' }
