$ErrorActionPreference = 'Stop'
$projectRoot = 'F:\JARVIS'
$overlayRoot = Join-Path $PSScriptRoot 'JARVIS'
$expectedVersion = '0.1.22'

if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
    throw "JARVIS project folder was not found: $projectRoot"
}

$required = @(
    'backend\app\main.py',
    'backend\app\imagegen_worker.py',
    'backend\app\poster_reference.py',
    'backend\tests\test_generated_image_history.py',
    'frontend\src\App.tsx',
    'frontend\src\api.ts',
    'frontend\src\imageIntent.ts',
    'frontend\tests\imageIntent.test.mjs',
    'frontend\package.json',
    'frontend\package-lock.json',
    'docs\CHANGELOG-v0.1.22.md'
)
foreach ($relative in $required) {
    $path = Join-Path $overlayRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Patch overlay is incomplete. Missing: $relative"
    }
}

$patchFiles = @(Get-ChildItem -LiteralPath $overlayRoot -Recurse -File)
if ($patchFiles.Count -lt 20) {
    throw "Patch overlay contains only $($patchFiles.Count) files; refusing an incomplete installation."
}

$backendSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'backend\app\main.py') -Raw
$packageSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'frontend\package.json') -Raw
if ($backendSource -notmatch 'version="0\.1\.22"' -or $packageSource -notmatch '"version"\s*:\s*"0\.1\.22"') {
    throw 'The patch files do not consistently identify themselves as v0.1.22.'
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.22-$stamp"
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
if ($installedPackage.version -ne $expectedVersion -or $installedBackend -notmatch 'version="0\.1\.22"') {
    throw "Post-install version verification failed. Restore files from: $backupRoot"
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.22 installed successfully.' -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
Write-Host 'Poster redesign phrases now dispatch to the local poster generator.' -ForegroundColor Green
Write-Host 'Repeated redesigns retain the original operator brief and choose a new composition.' -ForegroundColor Green
Write-Host 'Image previews are loaded only when their PNG/SVG files exist in the local manifest.' -ForegroundColor Green
Write-Host 'Text-only model replies cannot claim a verified image was created.' -ForegroundColor Green
Write-Host 'No models, runtimes, environments, or package dependencies were downloaded or replaced.' -ForegroundColor Gray
Write-Host 'Run backend tests and npm run test:image-intent before restarting JARVIS.' -ForegroundColor Yellow
