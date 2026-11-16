$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root 'environments\python\Scripts\python.exe'
$ModelDir = Join-Path $Root 'ai\models\kokoro'
$CacheDir = Join-Path $Root 'cache\pip'
$TempDir = Join-Path $Root 'cache\temp'
$ModelPath = Join-Path $ModelDir 'kokoro-v1.0.onnx'
$VoicesPath = Join-Path $ModelDir 'voices-v1.0.bin'

Write-Host ''
Write-Host 'J.A.R.V.I.S. — LOCAL NEURAL VOICE INSTALLER' -ForegroundColor Cyan
Write-Host 'Engine: Kokoro-82M ONNX (CPU; no cloud, no subscription, no API tokens)' -ForegroundColor Gray
Write-Host "Project: $Root" -ForegroundColor Gray
Write-Host "Model storage: $ModelDir" -ForegroundColor Gray
Write-Host ''

if (-not (Test-Path $Python)) {
    throw "Project Python environment not found: $Python. Run scripts\Setup-JARVIS.ps1 first."
}

$PyVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the project Python environment.' }
$VersionParts = $PyVersion.Split('.')
if ([int]$VersionParts[0] -ne 3 -or [int]$VersionParts[1] -lt 10 -or [int]$VersionParts[1] -ge 14) {
    throw "Kokoro-ONNX requires Python 3.10–3.13. This project environment reports Python $PyVersion."
}

New-Item -ItemType Directory -Force -Path $ModelDir, $CacheDir, $TempDir | Out-Null
$env:PIP_CACHE_DIR = $CacheDir
$env:TEMP = $TempDir
$env:TMP = $TempDir

$HasPackage = & $Python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('kokoro_onnx') else 1)"
if ($LASTEXITCODE -ne 0) {
    $Install = Read-Host 'Allow pip to download and install the free Kokoro Python package and its dependencies? (Y/N)'
    if ($Install -notin @('Y', 'y', 'YES', 'yes')) {
        throw 'Package installation declined. No package was installed.'
    }
    Write-Host 'Installing Kokoro-ONNX into the existing JARVIS virtual environment...' -ForegroundColor Cyan
    & $Python -m pip install --cache-dir $CacheDir 'kokoro-onnx==0.6.1'
    if ($LASTEXITCODE -ne 0) { throw 'Kokoro package installation failed. See the pip error above.' }
} else {
    Write-Host 'Kokoro Python package is already installed.' -ForegroundColor Green
}

if (-not ((Test-Path $ModelPath) -and (Test-Path $VoicesPath))) {
    $Download = Read-Host 'Allow download of the Kokoro neural voice model and voice pack (~300 MB) to F:\JARVIS? (Y/N)'
    if ($Download -notin @('Y', 'y', 'YES', 'yes')) {
        throw 'Model download declined. The neural voice remains unavailable until the model files are installed.'
    }

    $ModelUrl = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx'
    $VoicesUrl = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin'
    $ModelTemp = "$ModelPath.partial"
    $VoicesTemp = "$VoicesPath.partial"

    try {
        Write-Host 'Downloading Kokoro model (this is the larger file)...' -ForegroundColor Cyan
        Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelTemp -UseBasicParsing
        if ((Get-Item $ModelTemp).Length -lt 100MB) { throw 'Downloaded model file is unexpectedly small; the download may be incomplete.' }
        Move-Item -Force $ModelTemp $ModelPath

        Write-Host 'Downloading voice presets...' -ForegroundColor Cyan
        Invoke-WebRequest -Uri $VoicesUrl -OutFile $VoicesTemp -UseBasicParsing
        if ((Get-Item $VoicesTemp).Length -lt 1MB) { throw 'Downloaded voice pack is unexpectedly small; the download may be incomplete.' }
        Move-Item -Force $VoicesTemp $VoicesPath
    } catch {
        Remove-Item -Force -ErrorAction SilentlyContinue $ModelTemp, $VoicesTemp
        throw
    }
} else {
    Write-Host 'Kokoro model and voice pack are already present.' -ForegroundColor Green
}

Write-Host 'Verifying the local neural voice package...' -ForegroundColor Cyan
& $Python -c "from kokoro_onnx import Kokoro; print('Kokoro import: OK')"
if ($LASTEXITCODE -ne 0) { throw 'Kokoro could not be imported after installation.' }

if (-not ((Test-Path $ModelPath) -and (Test-Path $VoicesPath))) {
    throw 'The model files are still missing after installation.'
}

Write-Host ''
Write-Host 'Neural voice installation completed.' -ForegroundColor Green
Write-Host 'Default voice: George (British male). You can select Lewis, Michael, or Adam in the JARVIS dashboard.'
Write-Host 'Restart JARVIS, then click TEST VOICE once to hear the local neural voice.'
