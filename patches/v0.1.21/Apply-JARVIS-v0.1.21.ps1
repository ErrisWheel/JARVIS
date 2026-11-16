$ErrorActionPreference = 'Stop'
$projectRoot = 'F:\JARVIS'
$overlayRoot = Join-Path $PSScriptRoot 'JARVIS'
if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) { throw "JARVIS project folder was not found: $projectRoot" }
foreach ($required in @('backend\app\main.py','backend\app\imagegen_worker.py','backend\app\poster_reference.py','frontend\src\imageIntent.ts','frontend\src\App.tsx','frontend\package.json','frontend\tests\imageIntent.test.mjs')) {
    if (-not (Test-Path -LiteralPath (Join-Path $overlayRoot $required) -PathType Leaf)) { throw "Patch overlay is incomplete. Missing: $required" }
}
$patchFiles = @(Get-ChildItem -LiteralPath $overlayRoot -Recurse -File)
if ($patchFiles.Count -lt 18) { throw "Patch overlay contains only $($patchFiles.Count) files; refusing an incomplete installation." }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.21-$stamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
foreach ($file in $patchFiles) {
    $relative = $file.FullName.Substring($overlayRoot.Length).TrimStart('\')
    $destination = Join-Path $projectRoot $relative
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $backupPath = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupPath) -Force | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backupPath -Force
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
}
$package = Get-Content -LiteralPath (Join-Path $projectRoot 'frontend\package.json') -Raw | ConvertFrom-Json
if ($package.version -ne '0.1.21') { throw "Frontend version verification failed: $($package.version)" }
if ((Get-Content -LiteralPath (Join-Path $projectRoot 'backend\app\main.py') -Raw) -notmatch 'version="0\.1\.21"') { throw 'Backend version verification failed.' }
Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.21 installed successfully.' -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
Write-Host 'Long educational-poster briefs now route directly to local poster generation.' -ForegroundColor Green
Write-Host 'Poster jobs produce an inline PNG preview and an editable vector SVG download.' -ForegroundColor Green
Write-Host 'No models, environments or dependencies were downloaded or replaced.' -ForegroundColor Gray
Write-Host 'Run backend tests and frontend build before restarting JARVIS.' -ForegroundColor Yellow
