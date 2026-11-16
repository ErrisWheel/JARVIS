$ErrorActionPreference = 'Stop'

$patchRoot = $PSScriptRoot
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $patchRoot '..\..'))
$overlayRoot = Join-Path $patchRoot 'JARVIS'

if ((Split-Path -Leaf $projectRoot) -ne 'JARVIS') {
    throw "The patch must be extracted under F:\JARVIS\patches\v0.1.26. Resolved project root: $projectRoot"
}
if (-not (Test-Path -LiteralPath $overlayRoot -PathType Container)) {
    throw "Patch overlay folder is missing: $overlayRoot"
}

# Explicit allowlist: only these project source/test files can be replaced.
# This installer intentionally does not parse package-lock.json; PowerShell 5.1
# ConvertFrom-Json rejects npm's valid packages[""] root entry.
$relativeFiles = @(
    'backend\app\main.py',
    'backend\app\imagegen_worker.py',
    'backend\app\poster_reference.py',
    'backend\tests\test_landscape_poster.py',
    'frontend\src\App.tsx',
    'frontend\src\api.ts',
    'frontend\src\imageIntent.ts',
    'frontend\tests\imageIntent.test.mjs',
    'frontend\package.json',
    'frontend\package-lock.json'
)

foreach ($relative in $relativeFiles) {
    $candidate = Join-Path $overlayRoot $relative
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Required patch file is missing: $candidate"
    }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot ("backups\pre-v0.1.26-$timestamp")
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$copied = 0
foreach ($relative in $relativeFiles) {
    $source = Join-Path $overlayRoot $relative
    $destination = Join-Path $projectRoot $relative
    $destinationDirectory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null

    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $backupPath = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupPath) | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backupPath -Force
    }

    Copy-Item -LiteralPath $source -Destination $destination -Force
    $copied++
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.26 source patch applied.' -ForegroundColor Green
Write-Host "Files replaced: $copied"
Write-Host "Backup: $backupRoot"
Write-Host 'No model files, Python environments, Node modules, or configuration secrets were modified.' -ForegroundColor Cyan
