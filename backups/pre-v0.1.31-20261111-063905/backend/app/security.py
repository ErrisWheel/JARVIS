from pathlib import Path
import secrets
from .config import DATA_DIR, TOKEN_PATH, IMPORTS_DIR


def ensure_local_directories() -> None:
    for path in (DATA_DIR, IMPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        token = secrets.token_urlsafe(48)
        try:
            with TOKEN_PATH.open("x", encoding="utf-8") as f:
                f.write(token)
        except FileExistsError:
            pass


def load_api_token() -> str:
    ensure_local_directories()
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


def safe_import_path(name: str) -> Path:
    """Resolve a simple relative filename under imports; reject traversal and symlink escapes."""
    if not name or "\x00" in name:
        raise ValueError("A valid import filename is required")
    candidate = (IMPORTS_DIR / name).resolve(strict=False)
    base = IMPORTS_DIR.resolve(strict=True)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Path is outside the JARVIS imports folder") from exc
    if candidate == base:
        raise ValueError("A file name is required")
    return candidate
