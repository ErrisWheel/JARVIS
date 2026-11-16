$ErrorActionPreference = 'Stop'
$projectRoot = 'F:\JARVIS'
$overlayRoot = Join-Path $PSScriptRoot 'JARVIS'
$expectedVersion = '0.1.24'

if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
    throw "JARVIS project folder was not found: $projectRoot"
}

$requiredPatch = @(
    'backend\app\main.py',
    'backend\tests\test_image_artifact_validation.py',
    'frontend\src\App.tsx',
    'frontend\package.json',
    'frontend\package-lock.json',
    'docs\CHANGELOG-v0.1.24.md',
    'docs\INSTALL-v0.1.24.md'
)
foreach ($relative in $requiredPatch) {
    $path = Join-Path $overlayRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Patch overlay is incomplete. Missing: $relative"
    }
}

# These files are part of the existing poster pipeline and must remain present.
$requiredInstalled = @(
    'backend\app\imagegen_worker.py',
    'backend\app\poster_reference.py'
)
foreach ($relative in $requiredInstalled) {
    $path = Join-Path $projectRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required existing JARVIS poster component is missing: $relative. No files were changed."
    }
}

$backendSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'backend\app\main.py') -Raw
$frontendSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'frontend\src\App.tsx') -Raw
$packageSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'frontend\package.json') -Raw
$lockSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'frontend\package-lock.json') -Raw

if ($backendSource -notmatch 'version="0\.1\.24"' -or
    $packageSource -notmatch '"version"\s*:\s*"0\.1\.24"' -or
    $lockSource -notmatch '"version"\s*:\s*"0\.1\.24"') {
    throw 'The patch files do not consistently identify themselves as v0.1.24.'
}
if ($backendSource -notmatch 'def _validate_generated_svg' -or
    $backendSource -notmatch 'ET\.parse\(path\)') {
    throw 'The full-document SVG validation fix is missing.'
}
if ($backendSource -match 'svg_head\s*=\s*svg_file\.read_text\([^\r\n]+\)\[:2048\]') {
    throw 'The old 2 KB SVG-prefix validation is still present.'
}
if ($frontendSource -notmatch 'const index:\s*\{\s*png:\s*string\[\];\s*svg:\s*string\[\]\s*\}') {
    throw 'The generated-image index TypeScript annotation is missing.'
}

$patchFiles = @(Get-ChildItem -LiteralPath $overlayRoot -Recurse -File)
if ($patchFiles.Count -lt 7) {
    throw "Patch overlay contains only $($patchFiles.Count) files; refusing an incomplete installation."
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.24-$stamp"
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

$installedPackage = Get-Content -LiteralPath (Join-Path $projectRoot 'frontend\package.json') -Raw | ConvertFrom-Json
$installedBackend = Get-Content -LiteralPath (Join-Path $projectRoot 'backend\app\main.py') -Raw
$installedFrontend = Get-Content -LiteralPath (Join-Path $projectRoot 'frontend\src\App.tsx') -Raw
if ($installedPackage.version -ne $expectedVersion -or
    $installedBackend -notmatch 'version="0\.1\.24"' -or
    $installedFrontend -notmatch 'const index:\s*\{\s*png:\s*string\[\];\s*svg:\s*string\[\]\s*\}') {
    throw "Post-install verification failed. Restore files from: $backupRoot"
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.24 installed successfully.' -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
Write-Host 'High-density poster SVGs are now validated as complete XML documents.' -ForegroundColor Green
Write-Host 'The generated-image index TypeScript fallback is explicitly typed.' -ForegroundColor Green
Write-Host 'No models, runtimes, environments, or dependencies were downloaded or replaced.' -ForegroundColor Gray
Write-Host 'Run backend tests and npm run build before restarting JARVIS.' -ForegroundColor Yellow
