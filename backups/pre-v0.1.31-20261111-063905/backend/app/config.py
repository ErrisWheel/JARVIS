from pathlib import Path
import os

ROOT = Path(os.environ.get("JARVIS_ROOT", Path(__file__).resolve().parents[2])).resolve()
DATA_DIR = ROOT / "data"
IMPORTS_DIR = ROOT / "imports"
VOICE_MODEL_DIR = ROOT / "ai" / "models" / "whisper-base"
WAKE_MODEL_DIR = ROOT / "ai" / "models" / "wake-word"
LOGS_DIR = ROOT / "logs"
DB_PATH = DATA_DIR / "jarvis.sqlite3"
TOKEN_PATH = DATA_DIR / ".api_token"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("JARVIS_MODEL", "qwen3.5:9b")
MODEL_TEAM_REVIEWER = os.environ.get("JARVIS_REVIEW_MODEL", "qwen3:8b").strip() or "qwen3:8b"
API_HOST = "127.0.0.1"
API_PORT = 8787
TTS_MODEL_DIR = ROOT / "ai" / "models" / "kokoro"

IMAGE_MODEL_DIR = ROOT / "ai" / "models" / "sdxl-base-1.0"
IMAGE_OUTPUT_DIR = ROOT / "generated" / "images"
IMAGEGEN_PYTHON = ROOT / "environments" / "imagegen" / "Scripts" / "python.exe"
SELF_DEVELOPMENT_DIR = ROOT / "data" / "self_development"

EXPORTS_DIR = ROOT / "generated" / "exports"

# Optional local vision-language model. It is never downloaded automatically.
VISION_MODEL = os.environ.get("JARVIS_VISION_MODEL", "qwen2.5vl:7b").strip() or "qwen2.5vl:7b"
