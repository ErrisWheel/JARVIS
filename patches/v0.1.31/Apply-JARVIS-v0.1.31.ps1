# J.A.R.V.I.S. v0.1.31 integrated patch installer
# Windows PowerShell 5.1 compatible. No downloads, JSON parsing, or model changes.
$ErrorActionPreference = 'Stop'
$ProjectRoot = 'F:\JARVIS'
$ExpectedRoot = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
$PayloadRoot = Join-Path $PSScriptRoot 'payload'
$ManifestPath = Join-Path $PSScriptRoot 'MANIFEST.sha256'
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupRoot = Join-Path $ProjectRoot ("backups\pre-v0.1.31-" + $Timestamp)

function Test-ReparsePoint([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path -Force
        return (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
    }
    return $false
}

function Assert-NoReparsePath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    $drive = [System.IO.Path]::GetPathRoot($full)
    $current = $drive
    $relative = $full.Substring($drive.Length).TrimStart('\')
    foreach ($part in ($relative -split '\\')) {
        if ([string]::IsNullOrWhiteSpace($part)) { continue }
        $current = Join-Path $current $part
        if (Test-ReparsePoint $current) {
            throw "Refusing to access a symbolic link/junction/reparse point: $current"
        }
    }
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $ExpectedRoot -PathType Container)) {
    throw "Project root not found: $ExpectedRoot"
}
if ([System.IO.Path]::GetFullPath((Get-Item -LiteralPath $ExpectedRoot).FullName).TrimEnd('\') -ne $ExpectedRoot) {
    throw 'Unexpected project root resolution. Installation cancelled.'
}
if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container) -or
    -not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw 'Patch payload or MANIFEST.sha256 is missing. Re-extract the ZIP and retry.'
}

Assert-NoReparsePath $ExpectedRoot
Assert-NoReparsePath (Join-Path $ExpectedRoot 'frontend')
Assert-NoReparsePath (Join-Path $ExpectedRoot 'backend')

$PackagePath = Join-Path $ExpectedRoot 'frontend\package.json'
if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
    throw 'frontend/package.json was not found; this patch expects the JARVIS v0.1.29 or v0.1.30 source layout.'
}
$PackageText = Get-Content -LiteralPath $PackagePath -Raw
if ($PackageText -notmatch '"version"\s*:\s*"0\.1\.(29|30|31)"') {
    throw 'Frontend version is not 0.1.29, 0.1.30, or 0.1.31. Refusing to patch an unexpected source version.'
}

$Manifest = New-Object 'System.Collections.Generic.List[object]'
foreach ($line in (Get-Content -LiteralPath $ManifestPath)) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $separator = $line.IndexOf('|')
    if ($separator -ne 64) { throw "Invalid manifest line: $line" }
    $hash = $line.Substring(0, 64).ToLowerInvariant()
    $relative = $line.Substring(65).Replace('/', '\')
    if ($hash -notmatch '^[a-f0-9]{64}$' -or
        [string]::IsNullOrWhiteSpace($relative) -or
        [System.IO.Path]::IsPathRooted($relative) -or
        $relative -match '(^|\\)\.\.(\\|$)' -or
        $relative -match '^[A-Za-z]:') {
        throw "Unsafe or invalid manifest entry: $line"
    }
    $source = Join-Path $PayloadRoot $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Payload file is missing: $relative"
    }
    if ((Get-Sha256 $source) -ne $hash) {
        throw "Payload hash mismatch: $relative"
    }
    Assert-NoReparsePath $source
    $Manifest.Add([PSCustomObject]@{ Hash=$hash; Relative=$relative; Source=$source })
}
if ($Manifest.Count -eq 0) { throw 'The patch manifest is empty.' }

$PayloadFiles = @(Get-ChildItem -LiteralPath $PayloadRoot -File -Recurse -Force)
if ($PayloadFiles.Count -ne $Manifest.Count) {
    throw 'Payload contains unlisted files or the manifest is incomplete. Re-extract the original ZIP.'
}

# Verify each target path before writing any files.
foreach ($entry in $Manifest) {
    $target = Join-Path $ExpectedRoot $entry.Relative
    $parent = Split-Path -Parent $target
    Assert-NoReparsePath $parent
    if (Test-Path -LiteralPath $target) { Assert-NoReparsePath $target }
}

# Create and verify the project-local rollback directory.
$BackupParent = Join-Path $ExpectedRoot 'backups'
if (-not (Test-Path -LiteralPath $BackupParent)) {
    New-Item -ItemType Directory -Path $BackupParent -Force | Out-Null
}
Assert-NoReparsePath $BackupParent
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
Assert-NoReparsePath $BackupRoot

$Records = New-Object 'System.Collections.Generic.List[object]'
foreach ($entry in $Manifest) {
    $target = Join-Path $ExpectedRoot $entry.Relative
    $existed = Test-Path -LiteralPath $target -PathType Leaf
    $backup = Join-Path $BackupRoot $entry.Relative
    if ($existed) {
        $backupParent = Split-Path -Parent $backup
        New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
        Copy-Item -LiteralPath $target -Destination $backup -Force
        if ((Get-Sha256 $target) -ne (Get-Sha256 $backup)) {
            throw "Backup verification failed before installation: $($entry.Relative)"
        }
    }
    $Records.Add([PSCustomObject]@{ Target=$target; Backup=$backup; Existed=$existed; Relative=$entry.Relative })
}

try {
    foreach ($entry in $Manifest) {
        $target = Join-Path $ExpectedRoot $entry.Relative
        $targetParent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $targetParent)) {
            New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        }
        Assert-NoReparsePath $targetParent
        Copy-Item -LiteralPath $entry.Source -Destination $target -Force
        if ((Get-Sha256 $target) -ne $entry.Hash) {
            throw "Installed file hash mismatch: $($entry.Relative)"
        }
    }

    $installedPackage = Get-Content -LiteralPath $PackagePath -Raw
    if ($installedPackage -notmatch '"version"\s*:\s*"0\.1\.31"') {
        throw 'Post-install frontend version check failed.'
    }
    $mainPath = Join-Path $ExpectedRoot 'backend\app\main.py'
    $mainText = Get-Content -LiteralPath $mainPath -Raw
    if ($mainText -notmatch 'version="0\.1\.31"') {
        throw 'Post-install backend version check failed.'
    }
}
catch {
    Write-Host "Installation failed. Rolling back: $($_.Exception.Message)" -ForegroundColor Red
    $recordArray = $Records.ToArray()
    for ($i = $recordArray.Length - 1; $i -ge 0; $i--) {
        $record = $recordArray[$i]
        try {
            if ($record.Existed -and (Test-Path -LiteralPath $record.Backup -PathType Leaf)) {
                Copy-Item -LiteralPath $record.Backup -Destination $record.Target -Force
            } elseif (Test-Path -LiteralPath $record.Target -PathType Leaf) {
                Remove-Item -LiteralPath $record.Target -Force
            }
        } catch {
            Write-Host "ROLLBACK WARNING for $($record.Relative): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
    throw
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.31 installed successfully.' -ForegroundColor Green
Write-Host "Files installed: $($Manifest.Count)"
Write-Host "Backup location: $BackupRoot" -ForegroundColor Cyan
Write-Host 'No models, databases, environments, Node modules, or dependencies were downloaded or replaced.'
