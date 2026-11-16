# J.A.R.V.I.S. v0.1.41 cumulative source patch installer
# Compatible with Windows PowerShell 5.1. No JSON parsing, network access, or dependency install.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$ProjectRoot = 'F:\JARVIS'
$PayloadRoot = Join-Path $PSScriptRoot 'payload'
$ManifestPath = Join-Path $PSScriptRoot 'MANIFEST.sha256'
$TargetVersion = '0.1.41'
$AllowedVersions = @('0.1.29', '0.1.30', '0.1.31', '0.1.32', '0.1.40', '0.1.41')

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "JARVIS project root not found: $ProjectRoot"
}
if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) {
    throw "Patch payload not found: $PayloadRoot"
}
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw 'Patch manifest is missing.'
}

$RootFull = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
$PackagePath = Join-Path $RootFull 'frontend\package.json'
$BackendMainPath = Join-Path $RootFull 'backend\app\main.py'
if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
    throw 'frontend\package.json was not found. This patch expects an existing JARVIS installation.'
}

$PackageText = [System.IO.File]::ReadAllText($PackagePath)
$VersionMatch = [regex]::Match($PackageText, '"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $VersionMatch.Success) { throw 'Could not identify the installed frontend version.' }
$CurrentVersion = $VersionMatch.Groups[1].Value
if ($AllowedVersions -notcontains $CurrentVersion) {
    throw "Installed version $CurrentVersion is not supported by this cumulative patch. Expected one of: $($AllowedVersions -join ', ')."
}

$Entries = @()
$Seen = @{}
foreach ($Line in (Get-Content -LiteralPath $ManifestPath)) {
    if ([string]::IsNullOrWhiteSpace($Line)) { continue }
    if ($Line -notmatch '^([A-Fa-f0-9]{64})\s{2}(.+)$') {
        throw "Invalid manifest line: $Line"
    }
    $ExpectedHash = $Matches[1].ToLowerInvariant()
    $Relative = $Matches[2].Trim().Replace('/', '\')
    if ([System.IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|\\)\.\.(\\|$)' -or $Relative -match '^[A-Za-z]:') {
        throw "Unsafe relative path in patch manifest: $Relative"
    }
    if ($Seen.ContainsKey($Relative.ToLowerInvariant())) { throw "Duplicate manifest path: $Relative" }
    $Seen[$Relative.ToLowerInvariant()] = $true

    $SourcePath = [System.IO.Path]::GetFullPath((Join-Path $PayloadRoot $Relative))
    $PayloadPrefix = [System.IO.Path]::GetFullPath($PayloadRoot).TrimEnd('\') + '\'
    if (-not $SourcePath.StartsWith($PayloadPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Payload path escaped patch directory: $Relative"
    }
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Payload file is missing: $Relative"
    }
    $ActualHash = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) { throw "Payload hash mismatch: $Relative" }

    $TargetPath = [System.IO.Path]::GetFullPath((Join-Path $RootFull $Relative))
    $RootPrefix = $RootFull + '\'
    if (-not $TargetPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target path escaped JARVIS root: $Relative"
    }

    # Reject existing junctions/symlinks in the destination parent chain.
    $Parts = $Relative -split '\\'
    $Cursor = $RootFull
    for ($i = 0; $i -lt ($Parts.Length - 1); $i++) {
        $Cursor = Join-Path $Cursor $Parts[$i]
        if (Test-Path -LiteralPath $Cursor) {
            $ParentItem = Get-Item -LiteralPath $Cursor -Force
            if (($ParentItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing to write through a junction or symbolic link: $Cursor"
            }
        }
    }
    if (Test-Path -LiteralPath $TargetPath) {
        $TargetItem = Get-Item -LiteralPath $TargetPath -Force
        if ($TargetItem.PSIsContainer -or (($TargetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Refusing to replace a directory, junction, or symbolic link: $TargetPath"
        }
    }
    $Entries += [PSCustomObject]@{ Relative = $Relative; Source = $SourcePath; Target = $TargetPath; Hash = $ExpectedHash }
}
if ($Entries.Count -lt 20) { throw "Patch manifest looks incomplete ($($Entries.Count) files)." }

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$BackupRoot = Join-Path $RootFull "backups\JARVIS_v$TargetVersion`_$Stamp"
$BackupFiles = Join-Path $BackupRoot 'files'
New-Item -ItemType Directory -Force -Path $BackupFiles | Out-Null
$Applied = New-Object System.Collections.ArrayList

try {
    foreach ($Entry in $Entries) {
        $WasPresent = Test-Path -LiteralPath $Entry.Target -PathType Leaf
        $BackupPath = Join-Path $BackupFiles $Entry.Relative
        if ($WasPresent) {
            $BackupParent = Split-Path -Parent $BackupPath
            New-Item -ItemType Directory -Force -Path $BackupParent | Out-Null
            Copy-Item -LiteralPath $Entry.Target -Destination $BackupPath -Force
        }
        $null = $Applied.Add([PSCustomObject]@{ Target = $Entry.Target; Backup = $BackupPath; WasPresent = $WasPresent })
        $TargetParent = Split-Path -Parent $Entry.Target
        New-Item -ItemType Directory -Force -Path $TargetParent | Out-Null
        Copy-Item -LiteralPath $Entry.Source -Destination $Entry.Target -Force
    }

    foreach ($Entry in $Entries) {
        $InstalledHash = (Get-FileHash -LiteralPath $Entry.Target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($InstalledHash -ne $Entry.Hash) { throw "Installed file verification failed: $($Entry.Relative)" }
    }

    $FinalPackage = [System.IO.File]::ReadAllText($PackagePath)
    $FinalVersion = [regex]::Match($FinalPackage, '"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
    if (-not $FinalVersion.Success -or $FinalVersion.Groups[1].Value -ne $TargetVersion) {
        throw 'Frontend package version verification failed.'
    }
    $MainText = [System.IO.File]::ReadAllText($BackendMainPath)
    if ($MainText -notmatch 'version\s*=\s*"0\.1\.41"') {
        throw 'Backend version verification failed.'
    }
}
catch {
    Write-Warning 'Patch verification failed. Rolling back all replaced files.'
    for ($i = $Applied.Count - 1; $i -ge 0; $i--) {
        $Item = $Applied[$i]
        if ($Item.WasPresent -and (Test-Path -LiteralPath $Item.Backup -PathType Leaf)) {
            $Parent = Split-Path -Parent $Item.Target
            New-Item -ItemType Directory -Force -Path $Parent | Out-Null
            Copy-Item -LiteralPath $Item.Backup -Destination $Item.Target -Force
        } elseif (-not $Item.WasPresent -and (Test-Path -LiteralPath $Item.Target -PathType Leaf)) {
            Remove-Item -LiteralPath $Item.Target -Force
        }
    }
    throw
}

Write-Host ''
Write-Host 'J.A.R.V.I.S. v0.1.41 installed and verified.' -ForegroundColor Green
Write-Host "Files applied: $($Entries.Count)"
Write-Host "Previous version: $CurrentVersion"
Write-Host "Backup: $BackupRoot" -ForegroundColor Cyan
Write-Host 'No model files, databases, imports, environments, caches, or node_modules were replaced.'
Write-Host 'Run the frontend production build before restarting JARVIS.' -ForegroundColor Yellow
