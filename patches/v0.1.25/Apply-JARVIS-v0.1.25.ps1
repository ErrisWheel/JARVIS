$ErrorActionPreference = 'Stop'
$projectRoot = 'F:\JARVIS'
$overlayRoot = Join-Path $PSScriptRoot 'JARVIS'
$expectedVersion = '0.1.25'

function Read-JarvisPackageLock {
    param([Parameter(Mandatory = $true)][string]$Path)

    $jsonText = Get-Content -LiteralPath $Path -Raw
    # Windows PowerShell 5.1's ConvertFrom-Json rejects npm lockfiles whose
    # root package is stored under the valid empty key: "packages": { "": {} }.
    # Rename only that key for parsing; the original package-lock.json is copied
    # unchanged into the project.
    $compatibleJson = [regex]::Replace(
        $jsonText,
        '("packages"\s*:\s*\{)\s*""\s*:',
        '$1 "__JARVIS_ROOT_PACKAGE__":',
        1
    )
    if ($compatibleJson -eq $jsonText) {
        throw "Could not locate the npm root-package entry in package-lock.json: $Path"
    }

    try {
        return ConvertFrom-Json -InputObject $compatibleJson
    }
    catch {
        throw "Could not validate package-lock.json at '$Path': $($_.Exception.Message)"
    }
}

if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) {
    throw "JARVIS project folder was not found: $projectRoot"
}

$requiredPatch = @(
    'backend\app\main.py',
    'backend\tests\test_image_artifact_validation.py',
    'frontend\src\App.tsx',
    'frontend\package.json',
    'frontend\package-lock.json',
    'docs\CHANGELOG-v0.1.25.md',
    'docs\INSTALL-v0.1.25.md'
)
foreach ($relative in $requiredPatch) {
    $path = Join-Path $overlayRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Patch overlay is incomplete. Missing: $relative"
    }
}

# The installed project must already contain the poster engine from v0.1.23+.
$requiredInstalled = @(
    'backend\app\imagegen_worker.py',
    'backend\app\poster_reference.py'
)
foreach ($relative in $requiredInstalled) {
    $path = Join-Path $projectRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required existing JARVIS component is missing: $relative. No files were changed."
    }
}

$backendSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'backend\app\main.py') -Raw
$frontendSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'frontend\src\App.tsx') -Raw
$testSource = Get-Content -LiteralPath (Join-Path $overlayRoot 'backend\tests\test_image_artifact_validation.py') -Raw
$package = Get-Content -LiteralPath (Join-Path $overlayRoot 'frontend\package.json') -Raw | ConvertFrom-Json
$lock = Read-JarvisPackageLock -Path (Join-Path $overlayRoot 'frontend\package-lock.json')
$lockRootPackage = $lock.packages.PSObject.Properties['__JARVIS_ROOT_PACKAGE__'].Value

if ($backendSource -notmatch 'version="0\.1\.25"' -or
    $package.version -ne $expectedVersion -or
    $lock.version -ne $expectedVersion -or
    $null -eq $lockRootPackage -or
    $lockRootPackage.version -ne $expectedVersion) {
    throw 'The patch version declarations are inconsistent; no files were changed.'
}

$typedIndexCount = ([regex]::Matches(
    $frontendSource,
    'const index:\s*\{\s*png:\s*string\[\];\s*svg:\s*string\[\]\s*\}\s*=\s*await api\.generatedImagesIndex\(\)'
)).Count
if ($typedIndexCount -lt 2) {
    throw 'Both generated-image index declarations must explicitly use string[]; no files were changed.'
}
if ($frontendSource -notmatch 'index\.png\.includes\(imageReference\.filename\)') {
    throw 'The generated-image filename verification path was not found; no files were changed.'
}
if ($testSource -match '(?m)^\s*from\s+PIL\s+import\s+') {
    throw 'The artifact validation tests still import Pillow at module scope; no files were changed.'
}
if ($testSource -notmatch 'main\.IMAGEGEN_PYTHON') {
    throw 'The refinement integration test does not use the isolated image-generation interpreter.'
}

$patchFiles = @(Get-ChildItem -LiteralPath $overlayRoot -Recurse -File)
if ($patchFiles.Count -lt 7) {
    throw "Patch overlay contains only $($patchFiles.Count) files; refusing an incomplete installation."
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.25-$stamp"
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
$installedLock = Read-JarvisPackageLock -Path (Join-Path $projectRoot 'frontend\package-lock.json')
$installedLockRootPackage = $installedLock.packages.PSObject.Properties['__JARVIS_ROOT_PACKAGE__'].Value
$installedFrontend = Get-Content -LiteralPath (Join-Path $projectRoot 'frontend\src\App.tsx') -Raw
$installedTest = Get-Content -LiteralPath (Join-Path $projectRoot 'backend\tests\test_image_artifact_validation.py') -Raw
$installedTypedIndexCount = ([regex]::Matches(
    $installedFrontend,
    'const index:\s*\{\s*png:\s*string\[\];\s*svg:\s*string\[\]\s*\}\s*=\s*await api\.generatedImagesIndex\(\)'
)).Count

if ($installedPackage.version -ne $expectedVersion -or
    $installedLock.version -ne $expectedVersion -or
    $null -eq $installedLockRootPackage -or
    $installedLockRootPackage.version -ne $expectedVersion -or
    $installedTypedIndexCount -lt 2 -or
    $installedTest -match '(?m)^\s*from\s+PIL\s+import\s+') {
    throw "Post-install verification failed. Restore files from: $backupRoot"
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.25 installed successfully.' -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
Write-Host 'Both generated-image index fallbacks now use string[] instead of never[].' -ForegroundColor Green
Write-Host 'Artifact tests no longer require Pillow in the backend Python environment.' -ForegroundColor Green
Write-Host 'The refinement integration test uses the isolated image-generation Python environment when available.' -ForegroundColor Green
Write-Host 'No models, runtimes, environments, or dependencies were downloaded or replaced.' -ForegroundColor Gray
Write-Host 'Run npm run build and backend pytest before restarting JARVIS.' -ForegroundColor Yellow
