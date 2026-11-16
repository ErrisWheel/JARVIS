$ErrorActionPreference = 'Stop'

$patchRoot = $PSScriptRoot
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $patchRoot '..\..'))
$overlayRoot = Join-Path $patchRoot 'JARVIS'

if ((Split-Path -Leaf $projectRoot) -ne 'JARVIS') {
    throw "Extract this patch under F:\JARVIS\patches\v0.1.27. Resolved project root: $projectRoot"
}

$relative = 'frontend\src\App.tsx'
$source = Join-Path $overlayRoot $relative
$destination = Join-Path $projectRoot $relative
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Patch source is missing: $source"
}
if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
    throw "JARVIS target file is missing: $destination"
}

$sourceText = [System.IO.File]::ReadAllText($source)
if ($sourceText -notmatch 'function normalizeOrientation\(value: unknown\): VisualOrientation \| undefined') {
    throw 'Patch validation failed: orientation normalizer was not found.'
}
if (($sourceText.Split('normalizeOrientation(message.orientation) ?? reference.orientation').Length - 1) -ne 2) {
    throw 'Patch validation failed: both restored-history assignments are not normalized.'
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $projectRoot "backups\pre-v0.1.27-$timestamp"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent (Join-Path $backupRoot $relative)) | Out-Null
Copy-Item -LiteralPath $destination -Destination (Join-Path $backupRoot $relative) -Force
Copy-Item -LiteralPath $source -Destination $destination -Force

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.27 orientation restore type fix applied.' -ForegroundColor Green
Write-Host "File replaced: $relative"
Write-Host "Backup: $backupRoot"
Write-Host 'No package files, dependencies, models, environments, or configuration were modified.' -ForegroundColor Cyan
