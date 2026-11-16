$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Root.StartsWith('F:\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "JARVIS must be installed under F:\JARVIS for this project configuration. Found: $Root"
}
$CacheRoot = Join-Path $Root 'cache'
$EnvRoot = Join-Path $Root 'environments\imagegen'
$ModelRoot = Join-Path $Root 'ai\models\sdxl-base-1.0'
$TempRoot = Join-Path $CacheRoot 'tmp'
New-Item -ItemType Directory -Force -Path $CacheRoot, $TempRoot, $ModelRoot, (Join-Path $CacheRoot 'pip\imagegen'), (Join-Path $CacheRoot 'huggingface') | Out-Null
$env:PIP_CACHE_DIR = Join-Path $CacheRoot 'pip\imagegen'
$env:HF_HOME = Join-Path $CacheRoot 'huggingface'
$env:HF_HUB_CACHE = Join-Path $CacheRoot 'huggingface\hub'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:TMPDIR = $TempRoot
$env:TORCH_HOME = Join-Path $CacheRoot 'torch'
$env:XDG_CACHE_HOME = Join-Path $CacheRoot 'xdg'
$env:JARVIS_ROOT = $Root

$FreeGB = [math]::Round((Get-PSDrive -Name F).Free / 1GB, 1)
Write-Host "J.A.R.V.I.S. local image generation installer" -ForegroundColor Cyan
Write-Host "Project: $Root"
Write-Host "F: free space: $FreeGB GB"
Write-Host "The isolated image environment and model are stored under F:\JARVIS."
Write-Host "This installs local software and downloads SDXL model files. There is no hosted API or per-image fee."
Write-Host "Allow at least 18 GB of free space for the environment, model, and temporary downloads." -ForegroundColor Yellow
if ($FreeGB -lt 18) {
    throw "Only $FreeGB GB is free on F:. Free at least 18 GB before installing image generation. No model download was started."
}
Write-Host "Model license: CreativeML Open RAIL++-M. Review its use restrictions before enabling image generation." -ForegroundColor Yellow

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonLauncher) { throw 'Python Launcher (py.exe) was not found. Install Python 3.13 first.' }
& py -3.13 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 is required for the isolated image-generation environment.' }

$InstallDeps = Read-Host 'May I access the internet to install the local PyTorch CUDA 13.0 and Diffusers packages? (Y/N)'
if ($InstallDeps -notin @('Y','y','YES','yes')) {
    Write-Host 'Dependency installation cancelled. Nothing was downloaded.' -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path (Join-Path $EnvRoot 'Scripts\python.exe'))) {
    & py -3.13 -m venv $EnvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the image-generation virtual environment.' }
}
$ImagePython = Join-Path $EnvRoot 'Scripts\python.exe'
& $ImagePython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip in the image-generation environment.' }

Write-Host 'Installing PyTorch with CUDA 13.0 support for the RTX 5080...' -ForegroundColor Cyan
& $ImagePython -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw 'PyTorch CUDA installation failed. See the pip error above.' }
& $ImagePython -m pip install --upgrade diffusers transformers accelerate safetensors huggingface_hub
if ($LASTEXITCODE -ne 0) { throw 'Diffusers dependency installation failed. See the pip error above.' }

& $ImagePython -c "import torch; print('PyTorch:', torch.__version__); print('CUDA build:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not detected')"
if ($LASTEXITCODE -ne 0) { throw 'Could not validate the PyTorch installation.' }

if (-not (Test-Path (Join-Path $ModelRoot 'model_index.json'))) {
    $DownloadModel = Read-Host 'May I download the Stable Diffusion XL fp16 model (~7 GB) to F:\JARVIS\ai\models? (Y/N)'
    if ($DownloadModel -notin @('Y','y','YES','yes')) {
        Write-Host 'The runtime is installed, but image generation remains unavailable until the model is downloaded.' -ForegroundColor Yellow
        exit 0
    }
    $DownloadCode = @'
from huggingface_hub import snapshot_download
from pathlib import Path
import os
root = Path(os.environ["JARVIS_ROOT"]).resolve()
target = root / "ai" / "models" / "sdxl-base-1.0"
target.mkdir(parents=True, exist_ok=True)
allow = [
    "model_index.json", "LICENSE.md", "README.md",
    "scheduler/*", "feature_extractor/*",
    "text_encoder/config.json", "text_encoder/model.fp16.safetensors",
    "text_encoder_2/config.json", "text_encoder_2/model.fp16.safetensors",
    "tokenizer/*", "tokenizer_2/*",
    "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors",
    "vae/config.json", "vae/diffusion_pytorch_model.fp16.safetensors",
]
print("Downloading SDXL fp16 files. The download is stored only in the JARVIS model directory.")
snapshot_download(
    repo_id="stabilityai/stable-diffusion-xl-base-1.0",
    local_dir=str(target),
    allow_patterns=allow,
)
if not (target / "model_index.json").is_file():
    raise RuntimeError("The SDXL model download is incomplete.")
print(f"SDXL model downloaded to: {target}")
'@
    $env:JARVIS_ROOT = $Root
    $DownloadCode | & $ImagePython -
    if ($LASTEXITCODE -ne 0) { throw 'SDXL model download failed. Re-run this installer to resume.' }
}

if (Test-Path (Join-Path $ModelRoot 'model_index.json')) {
    Write-Host 'Image-generation runtime and local SDXL model are installed.' -ForegroundColor Green
    Write-Host 'At runtime JARVIS runs offline. During image generation it temporarily unloads active Ollama models to free GPU memory.' -ForegroundColor Cyan
} else {
    Write-Host 'Runtime installed; SDXL model is not installed yet.' -ForegroundColor Yellow
}
