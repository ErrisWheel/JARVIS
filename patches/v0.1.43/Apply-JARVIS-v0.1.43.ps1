# J.A.R.V.I.S. v0.1.43 - unified primary chat workspace + contextual image follow-up fix.
# Windows PowerShell 5.1 compatible. No network or dependency installation.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$ProjectRoot = 'F:\JARVIS'
$PayloadRoot = Join-Path $PSScriptRoot 'payload'
$ManifestPath = Join-Path $PSScriptRoot 'MANIFEST.sha256'
$TargetVersion = '0.1.43'
$AllowedVersions = @('0.1.42', '0.1.43')

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) { throw "JARVIS project root not found: $ProjectRoot" }
if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) { throw 'Patch payload is missing.' }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw 'Patch manifest is missing.' }

$RootFull = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
$PackagePath = Join-Path $RootFull 'frontend\package.json'
$BackendMainPath = Join-Path $RootFull 'backend\app\main.py'
if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) { throw 'frontend\package.json was not found.' }
if (-not (Test-Path -LiteralPath $BackendMainPath -PathType Leaf)) { throw 'backend\app\main.py was not found.' }

$PackageText = [System.IO.File]::ReadAllText($PackagePath)
$FrontendVersionMatch = [regex]::Match($PackageText, '"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $FrontendVersionMatch.Success) { throw 'Could not determine the installed frontend version.' }
$CurrentVersion = $FrontendVersionMatch.Groups[1].Value
if ($AllowedVersions -notcontains $CurrentVersion) { throw "Installed frontend version $CurrentVersion is not supported. Install v0.1.42 first." }

$BackendText = [System.IO.File]::ReadAllText($BackendMainPath)
$BackendVersionMatch = [regex]::Match($BackendText, 'version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $BackendVersionMatch.Success -or $BackendVersionMatch.Groups[1].Value -ne $CurrentVersion) {
    throw 'Frontend and backend versions do not match. Resolve the mismatch before applying this patch.'
}

$Entries = @()
$Seen = @{}
foreach ($Line in (Get-Content -LiteralPath $ManifestPath)) {
    if ([string]::IsNullOrWhiteSpace($Line)) { continue }
    if ($Line -notmatch '^([A-Fa-f0-9]{64})\s{2}(.+)$') { throw "Invalid manifest line: $Line" }
    $ExpectedHash = $Matches[1].ToLowerInvariant()
    $Relative = $Matches[2].Trim().Replace('/', '\')
    if ([System.IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|\\)\.\.(\\|$)' -or $Relative -match '^[A-Za-z]:') { throw "Unsafe relative path: $Relative" }
    $RelativeKey = $Relative.ToLowerInvariant()
    if ($Seen.ContainsKey($RelativeKey)) { throw "Duplicate manifest path: $Relative" }
    $Seen[$RelativeKey] = $true

    $SourcePath = [System.IO.Path]::GetFullPath((Join-Path $PayloadRoot $Relative))
    $PayloadPrefix = [System.IO.Path]::GetFullPath($PayloadRoot).TrimEnd('\') + '\'
    if (-not $SourcePath.StartsWith($PayloadPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Payload path escaped patch directory: $Relative" }
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) { throw "Payload file is missing: $Relative" }
    $ActualHash = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) { throw "Payload hash mismatch: $Relative" }

    $TargetPath = [System.IO.Path]::GetFullPath((Join-Path $RootFull $Relative))
    $RootPrefix = $RootFull + '\'
    if (-not $TargetPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Target path escaped JARVIS root: $Relative" }

    $Parts = $Relative -split '\\'
    $Cursor = $RootFull
    for ($i = 0; $i -lt ($Parts.Length - 1); $i++) {
        $Cursor = Join-Path $Cursor $Parts[$i]
        if (Test-Path -LiteralPath $Cursor) {
            $ParentItem = Get-Item -LiteralPath $Cursor -Force
            if (($ParentItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing to write through a junction or symbolic link: $Cursor" }
        }
    }
    if (Test-Path -LiteralPath $TargetPath) {
        $TargetItem = Get-Item -LiteralPath $TargetPath -Force
        if ($TargetItem.PSIsContainer -or (($TargetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) { throw "Refusing to replace a directory, junction, or symbolic link: $TargetPath" }
    }

    $Entries += [PSCustomObject]@{ Relative = $Relative; Source = $SourcePath; Target = $TargetPath; Hash = $ExpectedHash }
}
if ($Entries.Count -lt 10) { throw "Patch manifest appears incomplete ($($Entries.Count) files)." }

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
    $FinalFrontendVersion = [regex]::Match($FinalPackage, '"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
    if (-not $FinalFrontendVersion.Success -or $FinalFrontendVersion.Groups[1].Value -ne $TargetVersion) { throw 'Frontend package version verification failed.' }
    $FinalBackendText = [System.IO.File]::ReadAllText($BackendMainPath)
    if ($FinalBackendText -notmatch 'version\s*=\s*"0\.1\.43"') { throw 'Backend release version verification failed.' }
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
Write-Host 'J.A.R.V.I.S. v0.1.43 installed and verified.' -ForegroundColor Green
Write-Host "Files applied: $($Entries.Count)"
Write-Host "Previous version: $CurrentVersion"
Write-Host "Backup: $BackupRoot" -ForegroundColor Cyan
Write-Host 'Assistant is now the primary workspace; Memory, Ops, Self Development, System and Hologram share one rail.'
Write-Host 'Compound diagram guides and image-conversion follow-ups route to the local SDXL worker.'
Write-Host 'No models, databases, imports, generated images, Python environments, or node_modules were replaced.'
Write-Host 'Run npm run test:image-intent, npm run test:layout, and npm run build from F:\JARVIS\frontend.' -ForegroundColor Yellow
