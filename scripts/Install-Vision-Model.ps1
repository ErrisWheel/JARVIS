$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$modelTag = 'qwen2.5vl:7b'
$expectedStore = Join-Path $root 'ai\models\ollama'

Write-Host ''
Write-Host 'J.A.R.V.I.S. OPTIONAL LOCAL IMAGE-UNDERSTANDING MODEL' -ForegroundColor Cyan
Write-Host "Model: $modelTag"
Write-Host 'Approximate download size: 6 GB'
Write-Host 'Purpose: lets JARVIS inspect generated PNG images and answer questions about their visible contents.'
Write-Host 'Inference runs locally through Ollama. No image is uploaded to a hosted AI service.'
Write-Host ''

$ollamaCommand = Get-Command 'ollama' -ErrorAction SilentlyContinue
$ollamaExe = Join-Path $root 'runtime\ollama\ollama.exe'
if (Test-Path -LiteralPath $ollamaExe) {
    $ollama = $ollamaExe
} elseif ($ollamaCommand) {
    $ollama = $ollamaCommand.Source
} else {
    throw 'Ollama was not found. Install/configure the existing local JARVIS Ollama runtime first.'
}

$modelsSetting = [Environment]::GetEnvironmentVariable('OLLAMA_MODELS', 'User')
if (-not $modelsSetting) { $modelsSetting = $env:OLLAMA_MODELS }
if (-not $modelsSetting) {
    Write-Warning 'OLLAMA_MODELS is not set in the current user/session environment. The model could be stored outside F:\JARVIS.'
    $continue = Read-Host 'Continue only if you have confirmed the Ollama service stores models under F:\JARVIS\ai\models\ollama. Type YES'
    if ($continue -cne 'YES') { Write-Host 'Cancelled. No model was downloaded.'; exit 0 }
} elseif ([IO.Path]::GetFullPath($modelsSetting).TrimEnd('\') -ine [IO.Path]::GetFullPath($expectedStore).TrimEnd('\')) {
    throw "OLLAMA_MODELS currently points to '$modelsSetting', not '$expectedStore'. Refusing to download outside F:\JARVIS. Correct the Ollama model location first."
}

$drive = Get-PSDrive -Name F -ErrorAction Stop
if ($drive.Free -lt 8GB) {
    throw 'At least 8 GB of free space on F: is recommended before downloading this model.'
}

Write-Host 'This step requires internet access to download the approved open model from the Ollama model library.' -ForegroundColor Yellow
$approval = Read-Host "Download $modelTag now? Type YES"
if ($approval -cne 'YES') {
    Write-Host 'Cancelled. No model was downloaded.' -ForegroundColor Yellow
    exit 0
}

Write-Host "Pulling $modelTag through the local Ollama installation..." -ForegroundColor Cyan
& $ollama pull $modelTag
if ($LASTEXITCODE -ne 0) {
    throw "Ollama model download failed with exit code $LASTEXITCODE. No JARVIS configuration was changed."
}

Write-Host ''
Write-Host 'Vision model installation completed.' -ForegroundColor Green
Write-Host 'Restart the JARVIS backend, then ask it to describe a recently generated image.'
