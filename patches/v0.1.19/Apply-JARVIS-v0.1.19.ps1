$ErrorActionPreference = 'Stop'

$projectRoot = 'F:\JARVIS'
$overlayRoot = Join-Path $PSScriptRoot 'JARVIS'

if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
    throw "JARVIS project folder was not found: $projectRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $overlayRoot 'backend\app\main.py') -PathType Leaf)) {
    throw "Patch overlay is incomplete. Expected: $overlayRoot\backend\app\main.py"
}
if (-not (Test-Path -LiteralPath (Join-Path $overlayRoot 'backend\app\imagegen_worker.py') -PathType Leaf)) {
    throw 'Poster renderer is missing from the patch. Nothing was installed.'
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.19-$stamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$patchFiles = @(Get-ChildItem -LiteralPath $overlayRoot -Recurse -File)
if ($patchFiles.Count -lt 10) {
    throw "Patch overlay contains only $($patchFiles.Count) files; refusing an incomplete installation."
}

foreach ($file in $patchFiles) {
    $relative = $file.FullName.Substring($overlayRoot.Length).TrimStart('\')
    $destination = Join-Path $projectRoot $relative

    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $backupPath = Join-Path $backupRoot $relative
        $backupDirectory = Split-Path -Parent $backupPath
        New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backupPath -Force
    }

    $destinationDirectory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
}

$packagePath = Join-Path $projectRoot 'frontend\package.json'
$package = Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json
if ($package.version -ne '0.1.19') {
    throw "Frontend version verification failed. Found: $($package.version)"
}

$mainPath = Join-Path $projectRoot 'backend\app\main.py'
$mainSource = Get-Content -LiteralPath $mainPath -Raw
if ($mainSource -notmatch 'version="0\.1\.19"') {
    throw 'Backend version verification failed. Check backend\app\main.py.'
}
$workerPath = Join-Path $projectRoot 'backend\app\imagegen_worker.py'
$workerSource = Get-Content -LiteralPath $workerPath -Raw
if ($workerSource -notmatch '_render_educational_poster') {
    throw 'Poster renderer verification failed.'
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.19 installed successfully.' -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
Write-Host 'Poster text is now rendered locally with real font glyphs; SDXL is not used for poster typography.' -ForegroundColor Green
Write-Host 'Existing SDXL, Ollama models, Python environments, Node dependencies, databases, and generated images were not replaced.' -ForegroundColor Gray
Write-Host 'Run the backend tests and frontend build before restarting JARVIS.' -ForegroundColor Yellow
