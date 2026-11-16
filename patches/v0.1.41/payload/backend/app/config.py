from pathlib import Path
from ipaddress import ip_address
from urllib.parse import urlsplit
import os

ROOT = Path(os.environ.get("JARVIS_ROOT", Path(__file__).resolve().parents[2])).resolve()
DATA_DIR = ROOT / "data"
IMPORTS_DIR = ROOT / "imports"
VOICE_MODEL_DIR = ROOT / "ai" / "models" / "whisper-base"
WAKE_MODEL_DIR = ROOT / "ai" / "models" / "wake-word"
LOGS_DIR = ROOT / "logs"
DB_PATH = DATA_DIR / "jarvis.sqlite3"
TOKEN_PATH = DATA_DIR / ".api_token"
def _validate_local_ollama_base_url(value: str | None) -> str:
    """Accept Ollama only over plain HTTP on a loopback address.

    JARVIS is a local-only application. Allowing an environment override to point
    at a LAN or internet host would silently turn local inference into remote
    network access, so reject every non-loopback target at startup.
    """
    raw = (value or "http://127.0.0.1:11434").strip().rstrip("/")
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        # Accessing .port also validates malformed/out-of-range port values.
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("OLLAMA_BASE_URL is invalid; use http://127.0.0.1:11434 or another localhost URL.") from exc

    if (
        parsed.scheme.casefold() != "http"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "OLLAMA_BASE_URL must be a plain HTTP loopback URL without credentials, path, query, or fragment."
        )

    if hostname.casefold() != "localhost":
        try:
            address = ip_address(hostname)
        except ValueError as exc:
            raise ValueError("OLLAMA_BASE_URL must target localhost or a loopback IP address; remote hosts are blocked.") from exc
        if not address.is_loopback:
            raise ValueError("OLLAMA_BASE_URL must target localhost or a loopback IP address; remote hosts are blocked.")

    # Keep IPv6 brackets, explicit ports and standard URL casing intact.
    return f"http://{parsed.netloc}"


OLLAMA_BASE_URL = _validate_local_ollama_base_url(os.environ.get("OLLAMA_BASE_URL"))
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
