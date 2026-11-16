$ErrorActionPreference = 'Stop'
$Root = 'F:\JARVIS'
if ((Get-Location).Path -ine $Root) { throw "Run this script from F:\JARVIS. Current folder: $((Get-Location).Path)" }
$Python = Join-Path $Root 'environments\python\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'JARVIS Python environment not found. Run .\scripts\Setup-JARVIS.ps1 first.' }
$env:JARVIS_ROOT = $Root
$env:TEMP = Join-Path $Root 'cache\temp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $Root 'cache\pip'
$env:HF_HOME = Join-Path $Root 'ai\cache\huggingface'
$WhisperDir = Join-Path $Root 'ai\models\whisper-base'
$WakeDir = Join-Path $Root 'ai\models\wake-word'
New-Item -ItemType Directory -Force $env:TEMP, $env:PIP_CACHE_DIR, $env:HF_HOME, $WhisperDir, $WakeDir | Out-Null

Write-Host 'Checking local voice dependencies…' -ForegroundColor Cyan
& $Python -c 'import faster_whisper, multipart, openwakeword, sounddevice, av, sys; sys.exit(0 if int(av.__version__.split(".")[0]) < 19 else 1)'
if ($LASTEXITCODE -ne 0) {
    Write-Host 'This installs local speech recognition, wake-word detection, and microphone capture packages into F:\JARVIS.' -ForegroundColor Yellow
    $answer = Read-Host 'Allow internet access to install these Python packages? (Y/N)'
    if ($answer -notin @('Y','y','YES','yes')) { Write-Host 'Cancelled. No network request was made.'; exit 0 }
    & $Python -m pip install 'faster-whisper>=1.1,<2' 'av>=11,<19' 'python-multipart>=0.0.20,<1' 'openwakeword>=0.6.0,<1' 'sounddevice>=0.5.2,<1' --cache-dir $env:PIP_CACHE_DIR
    if ($LASTEXITCODE -ne 0) { throw 'Voice dependency installation failed.' }
}

if (-not (Test-Path (Join-Path $WhisperDir 'model.bin'))) {
    Write-Host 'The multilingual Whisper base model is approximately 150 MB. It supports English and many languages; transcription runs locally on the CPU.' -ForegroundColor Yellow
    $answer = Read-Host 'Allow internet access to download Whisper into F:\JARVIS\ai\models\whisper-base? (Y/N)'
    if ($answer -notin @('Y','y','YES','yes')) { Write-Host 'Whisper model download cancelled.' -ForegroundColor Yellow; exit 0 }
    $env:JARVIS_WHISPER_MODEL_DIR = $WhisperDir
    @'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Systran/faster-whisper-base",
    local_dir=os.environ["JARVIS_WHISPER_MODEL_DIR"],
)
print("Local Whisper model downloaded.")
'@ | & $Python -
    if ($LASTEXITCODE -ne 0) { throw 'Whisper model download failed.' }
}

if (-not (Test-Path (Join-Path $WakeDir 'hey_jarvis_v0.1.onnx')) -or -not (Test-Path (Join-Path $WakeDir 'melspectrogram.onnx')) -or -not (Test-Path (Join-Path $WakeDir 'embedding_model.onnx'))) {
    Write-Host 'JARVIS can listen locally for the wake phrase “Hey Jarvis”. This is an audio wake-word model, not a search for the word JARVIS in normal speech.' -ForegroundColor Yellow
    Write-Host 'The small pretrained English detector and feature models will be downloaded from the official openWakeWord GitHub release.' -ForegroundColor Yellow
    $answer = Read-Host 'Allow internet access to download the wake-word model into F:\JARVIS\ai\models\wake-word? (Y/N)'
    if ($answer -notin @('Y','y','YES','yes')) { Write-Host 'Wake-word download cancelled. Push-to-talk transcription remains available.' -ForegroundColor Yellow; exit 0 }
    $env:JARVIS_WAKE_MODEL_DIR = $WakeDir
    @'
import os
from openwakeword.utils import download_models
download_models(model_names=["hey_jarvis"], target_directory=os.environ["JARVIS_WAKE_MODEL_DIR"])
print("Hey Jarvis wake-word models downloaded.")
'@ | & $Python -
    if ($LASTEXITCODE -ne 0) { throw 'Wake-word model download failed.' }
}

Write-Host 'Local voice input and Hey JARVIS wake-word support are installed.' -ForegroundColor Green
Write-Host "Whisper model directory: $WhisperDir"
Write-Host "Wake-word model directory: $WakeDir"
Write-Host 'Restart JARVIS, then enable Hey JARVIS in the dashboard. The microphone remains off until you enable it.' -ForegroundColor Cyan
