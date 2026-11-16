$ErrorActionPreference = 'Stop'

$projectRoot = 'F:\JARVIS'
$overlayRoot = Join-Path $PSScriptRoot 'JARVIS'

if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
    throw "JARVIS project folder was not found: $projectRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $overlayRoot 'backend\app\main.py') -PathType Leaf)) {
    throw "Patch overlay is incomplete. Expected: $overlayRoot\backend\app\main.py"
}
if (-not (Test-Path -LiteralPath (Join-Path $overlayRoot 'frontend\src\Hologram.tsx') -PathType Leaf)) {
    throw 'Patch overlay is incomplete. Hologram.tsx is missing.'
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.18-$stamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$files = Get-ChildItem -LiteralPath $overlayRoot -Recurse -File
if (-not $files) { throw 'The patch contains no files.' }

foreach ($file in $files) {
    $relative = $file.FullName.Substring($overlayRoot.Length).TrimStart('\')
    $destination = Join-Path $projectRoot $relative
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $backup = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backup -Force
    }
}

foreach ($file in $files) {
    $relative = $file.FullName.Substring($overlayRoot.Length).TrimStart('\')
    $destination = Join-Path $projectRoot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    Write-Host "Updated $relative" -ForegroundColor DarkGray
}

$frontendManifest = Get-Content -LiteralPath (Join-Path $projectRoot 'frontend\package.json') -Raw | ConvertFrom-Json
$backendSource = Get-Content -LiteralPath (Join-Path $projectRoot 'backend\app\main.py') -Raw
if ($frontendManifest.version -ne '0.1.18' -or $backendSource -notmatch 'version="0\.1\.18"') {
    throw 'Post-install version verification failed. Restore from the backup before starting JARVIS.'
}

Write-Host "`nJARVIS v0.1.18 installed successfully." -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
Write-Host 'No model files, Python environments, Node dependencies, or user data were changed.' -ForegroundColor Green
