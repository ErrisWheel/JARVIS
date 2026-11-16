$ErrorActionPreference = 'Stop'

# J.A.R.V.I.S. v0.1.29 patch installer for Windows PowerShell 5.1.
# Deliberately avoids ConvertFrom-Json so npm lockfiles with empty keys remain compatible.
$ProjectRoot = 'F:\JARVIS'
$PayloadRoot = Join-Path $PSScriptRoot 'payload'

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "JARVIS project folder was not found at $ProjectRoot. This patch is configured for the existing F:\JARVIS installation."
}
if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) {
    throw "Patch payload folder is missing beside this installer: $PayloadRoot"
}

$RelativeFiles = @(
    'frontend\src\App.tsx',
    'frontend\src\imageIntent.ts',
    'frontend\tests\imageIntent.test.mjs',
    'frontend\package.json',
    'frontend\package-lock.json',
    'docs\CHANGELOG-v0.1.29.md'
)

foreach ($RelativePath in $RelativeFiles) {
    $SourcePath = Join-Path $PayloadRoot $RelativePath
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Patch is incomplete. Missing payload file: $RelativePath"
    }
}

$AppPatch = Get-Content -LiteralPath (Join-Path $PayloadRoot 'frontend\src\App.tsx') -Raw
if ($AppPatch -notmatch 'const normalizedMessage\s*=\s*\{' -or
    $AppPatch -notmatch 'const restored:\s*ChatLine\[\]') {
    throw 'Patch validation failed: the normalized conversation restore code is missing.'
}

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupRoot = Join-Path $ProjectRoot ("backups\pre-v0.1.29-" + $Stamp)
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

# Back up all existing destination files before changing anything.
foreach ($RelativePath in $RelativeFiles) {
    $DestinationPath = Join-Path $ProjectRoot $RelativePath
    if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
        $BackupPath = Join-Path $BackupRoot $RelativePath
        $BackupDirectory = Split-Path -Parent $BackupPath
        New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
        Copy-Item -LiteralPath $DestinationPath -Destination $BackupPath -Force
    }
}

try {
    foreach ($RelativePath in $RelativeFiles) {
        $SourcePath = Join-Path $PayloadRoot $RelativePath
        $DestinationPath = Join-Path $ProjectRoot $RelativePath
        $DestinationDirectory = Split-Path -Parent $DestinationPath
        New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
    }
} catch {
    Write-Warning 'Patch copy failed. Attempting to restore the pre-patch files.'
    foreach ($RelativePath in $RelativeFiles) {
        $BackupPath = Join-Path $BackupRoot $RelativePath
        $DestinationPath = Join-Path $ProjectRoot $RelativePath
        if (Test-Path -LiteralPath $BackupPath -PathType Leaf) {
            Copy-Item -LiteralPath $BackupPath -Destination $DestinationPath -Force
        }
    }
    throw
}

# Verify the exact source-level fix after copying.
$InstalledApp = Get-Content -LiteralPath (Join-Path $ProjectRoot 'frontend\src\App.tsx') -Raw
if ($InstalledApp -notmatch 'const normalizedMessage\s*=\s*\{' -or
    $InstalledApp -notmatch 'const restored:\s*ChatLine\[\]') {
    throw "Post-install verification failed. Original files are backed up at $BackupRoot"
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.29 patch installed successfully.' -ForegroundColor Green
Write-Host "Backup: $BackupRoot" -ForegroundColor Cyan
Write-Host 'No models, Python environments, Node modules, databases, or generated images were changed.' -ForegroundColor Cyan
Write-Host 'Next: run npm run build from F:\JARVIS\frontend.' -ForegroundColor Yellow
