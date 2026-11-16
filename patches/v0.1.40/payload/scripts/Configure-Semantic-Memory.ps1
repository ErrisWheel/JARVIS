$ErrorActionPreference = 'Stop'
$Root = 'F:\JARVIS'
if (-not (Test-Path -LiteralPath $Root -PathType Container)) { throw "JARVIS root not found: $Root" }
$Ollama = Join-Path $Root 'runtime\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $Ollama)) {
    $Command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($Command) { $Ollama = $Command.Source } else { throw 'Ollama was not found. Start or install the existing local Ollama runtime first.' }
}
Write-Host 'Reading models already installed locally. This script will NOT download anything.' -ForegroundColor Cyan
$Output = & $Ollama list 2>&1
if ($LASTEXITCODE -ne 0) { throw "Could not query local Ollama models: $Output" }
$Names = @($Output | ForEach-Object { if ($_ -match '^\s*([A-Za-z0-9._/-]+:[A-Za-z0-9._-]+)\s+') { $Matches[1] } })
$Candidates = @($Names | Where-Object { $_ -match '(?i)(embed|embedding)' })
if ($Candidates.Count -eq 0) {
    Write-Host ''
    Write-Host 'No installed model name clearly identifies itself as an embedding model.' -ForegroundColor Yellow
    Write-Host 'Install an embedding model separately only after explicitly approving the local download.'
    Write-Host 'Then run this configuration script again.'
    exit 2
}
Write-Host ''
Write-Host 'Installed embedding-model candidates:' -ForegroundColor Green
for ($i = 0; $i -lt $Candidates.Count; $i++) { Write-Host ("[{0}] {1}" -f ($i + 1), $Candidates[$i]) }
$Choice = Read-Host 'Enter the number of the embedding model to use (blank cancels)'
if ([string]::IsNullOrWhiteSpace($Choice)) { Write-Host 'No changes made.'; exit 0 }
$Index = 0
if (-not [int]::TryParse($Choice, [ref]$Index) -or $Index -lt 1 -or $Index -gt $Candidates.Count) { throw 'Invalid model selection.' }
$Selected = $Candidates[$Index - 1]
$ConfigDir = Join-Path $Root 'data'
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$ConfigPath = Join-Path $ConfigDir 'semantic-embedding-model.txt'
[System.IO.File]::WriteAllText($ConfigPath, $Selected + [Environment]::NewLine, ([System.Text.UTF8Encoding]::new($false)))
Write-Host "Configured local semantic memory model: $Selected" -ForegroundColor Green
Write-Host 'Restart JARVIS to load this setting, open MEMORY, and select REINDEX.'
