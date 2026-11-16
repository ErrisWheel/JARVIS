from pathlib import Path
import secrets
from .config import ROOT, DATA_DIR, TOKEN_PATH, IMPORTS_DIR


def _is_link_or_junction(path: Path) -> bool:
    """Detect symlinks and Windows directory junctions/reparse-point aliases."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    try:
        return bool(is_junction()) if callable(is_junction) else False
    except OSError:
        return True


def _ensure_project_child(path: Path) -> Path:
    """Create a managed directory only when it resolves beneath the project root."""
    root = ROOT.resolve(strict=True)
    if _is_link_or_junction(path):
        raise RuntimeError(f"JARVIS-managed directory must not be a symbolic link: {path.name}")
    path.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"JARVIS-managed directory resolves outside the project root: {path}") from exc
    return resolved


def ensure_local_directories() -> None:
    for path in (DATA_DIR, IMPORTS_DIR):
        _ensure_project_child(path)
    if _is_link_or_junction(TOKEN_PATH):
        raise RuntimeError("The local API token file must not be a symbolic link or junction.")
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
    r"""Resolve an imported file under F:\JARVIS\imports without link or traversal escapes."""
    if not name or "\x00" in name:
        raise ValueError("A valid import filename is required")
    relative = Path(name)
    if relative.is_absolute() or any(part in {"..", ""} for part in relative.parts):
        raise ValueError("Only a relative filename inside the JARVIS imports folder is allowed")
    if _is_link_or_junction(IMPORTS_DIR):
        raise ValueError("The JARVIS imports folder must not be a symbolic link")
    root = ROOT.resolve(strict=True)
    base = IMPORTS_DIR.resolve(strict=True)
    try:
        base.relative_to(root)
    except ValueError as exc:
        raise ValueError("The JARVIS imports folder resolves outside the project root") from exc
    candidate_path = IMPORTS_DIR / relative
    # Reject symbolic links in any path component, even when the target happens
    # to remain under imports; this avoids surprising aliases and TOCTOU escapes.
    current = IMPORTS_DIR
    for part in relative.parts:
        current = current / part
        if _is_link_or_junction(current):
            raise ValueError("Symbolic links are not allowed in the JARVIS imports folder")
    candidate = candidate_path.resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Path is outside the JARVIS imports folder") from exc
    if candidate == base:
        raise ValueError("A file name is required")
    return candidate
