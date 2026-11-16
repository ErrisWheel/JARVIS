# J.A.R.V.I.S. v0.1.42 incremental image-routing hotfix.
# Windows PowerShell 5.1 compatible; no network access or dependency installation.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$ProjectRoot = 'F:\JARVIS'
$PayloadRoot = Join-Path $PSScriptRoot 'payload'
$ManifestPath = Join-Path $PSScriptRoot 'MANIFEST.sha256'
$TargetVersion = '0.1.42'
$AllowedVersions = @('0.1.41', '0.1.42')

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "JARVIS project root not found: $ProjectRoot"
}
if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) {
    throw 'Patch payload is missing.'
}
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw 'Patch manifest is missing.'
}

$RootFull = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
$PackagePath = Join-Path $RootFull 'frontend\package.json'
$BackendMainPath = Join-Path $RootFull 'backend\app\main.py'
if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
    throw 'frontend\package.json was not found. This patch requires an existing JARVIS installation.'
}
if (-not (Test-Path -LiteralPath $BackendMainPath -PathType Leaf)) {
    throw 'backend\app\main.py was not found.'
}

$PackageText = [System.IO.File]::ReadAllText($PackagePath)
$VersionMatch = [regex]::Match($PackageText, '"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $VersionMatch.Success) { throw 'Could not determine the installed frontend version.' }
$CurrentVersion = $VersionMatch.Groups[1].Value
if ($AllowedVersions -notcontains $CurrentVersion) {
    throw "Installed frontend version $CurrentVersion is not supported. This hotfix requires v0.1.41 or v0.1.42."
}
$BackendText = [System.IO.File]::ReadAllText($BackendMainPath)
$BackendVersionMatch = [regex]::Match($BackendText, 'version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $BackendVersionMatch.Success -or $BackendVersionMatch.Groups[1].Value -ne $CurrentVersion) {
    throw 'Frontend and backend release versions do not match. Resolve the version mismatch before applying this patch.'
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
    $RelativeKey = $Relative.ToLowerInvariant()
    if ($Seen.ContainsKey($RelativeKey)) { throw "Duplicate manifest path: $Relative" }
    $Seen[$RelativeKey] = $true

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

    # Refuse writes through any existing reparse point in the destination chain.
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

    $Entries += [PSCustomObject]@{
        Relative = $Relative
        Source = $SourcePath
        Target = $TargetPath
        Hash = $ExpectedHash
    }
}
if ($Entries.Count -lt 8) { throw "Patch manifest appears incomplete ($($Entries.Count) files)." }

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
        $null = $Applied.Add([PSCustomObject]@{
            Target = $Entry.Target
            Backup = $BackupPath
            WasPresent = $WasPresent
        })
        $TargetParent = Split-Path -Parent $Entry.Target
        New-Item -ItemType Directory -Force -Path $TargetParent | Out-Null
        Copy-Item -LiteralPath $Entry.Source -Destination $Entry.Target -Force
    }

    foreach ($Entry in $Entries) {
        $InstalledHash = (Get-FileHash -LiteralPath $Entry.Target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($InstalledHash -ne $Entry.Hash) { throw "Installed file verification failed: $($Entry.Relative)" }
    }

    $FinalPackage = [System.IO.File]::ReadAllText($PackagePath)
    $FinalFrontendVersion = [regex]::Match($FinalPackage, '"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
    if (-not $FinalFrontendVersion.Success -or $FinalFrontendVersion.Groups[1].Value -ne $TargetVersion) {
        throw 'Frontend package version verification failed.'
    }
    $FinalBackendText = [System.IO.File]::ReadAllText($BackendMainPath)
    if ($FinalBackendText -notmatch 'version\s*=\s*"0\.1\.42"') {
        throw 'Backend release version verification failed.'
    }
}
catch {
    Write-Warning 'Patch verification failed. Rolling back every applied file.'
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
Write-Host 'J.A.R.V.I.S. v0.1.42 image-routing hotfix installed and verified.' -ForegroundColor Green
Write-Host "Files applied: $($Entries.Count)"
Write-Host "Previous version: $CurrentVersion"
Write-Host "Backup: $BackupRoot" -ForegroundColor Cyan
Write-Host 'Generic diagrams now use SDXL; explicit posters/infographics retain precise typography.'
Write-Host 'No models, databases, imports, generated images, environments, or node_modules were replaced.'
Write-Host 'Run npm run build and npm run test:image-intent from F:\JARVIS\frontend before restarting.' -ForegroundColor Yellow
