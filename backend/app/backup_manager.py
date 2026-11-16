"""Versioned, project-local SQLite snapshots with explicit restore confirmation."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .config import DB_PATH, DATA_DIR

BACKUP_DIR = DATA_DIR / "backups"
BACKUP_NAME = re.compile(r"^jarvis-db-\d{8}-\d{6}\.sqlite3$")


def _safe_backup_dir() -> Path:
    root = DATA_DIR.resolve(strict=True)
    if BACKUP_DIR.is_symlink():
        raise RuntimeError("The backup directory cannot be a symbolic link.")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    resolved = BACKUP_DIR.resolve(strict=True)
    resolved.relative_to(root)
    return resolved


def safe_backup_path(filename: str, *, must_exist: bool = True) -> Path:
    if not BACKUP_NAME.fullmatch(filename):
        raise ValueError("Invalid backup filename.")
    folder = _safe_backup_dir()
    candidate = folder / filename
    if candidate.is_symlink():
        raise ValueError("Backup path cannot be a symbolic link.")
    if must_exist and not candidate.is_file():
        raise FileNotFoundError("Backup not found.")
    resolved = candidate.resolve(strict=must_exist)
    resolved.relative_to(folder)
    return resolved


def create_backup() -> dict:
    folder = _safe_backup_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"jarvis-db-{stamp}.sqlite3"
    target = folder / filename
    with sqlite3.connect(DB_PATH) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
        result = destination.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            target.unlink(missing_ok=True)
            raise RuntimeError("SQLite backup failed its integrity check.")
    return {"filename": filename, "size_bytes": target.stat().st_size, "created_at": datetime.now(timezone.utc).isoformat()}


def list_backups() -> list[dict]:
    folder = _safe_backup_dir()
    entries=[]
    for path in folder.iterdir():
        if path.is_file() and not path.is_symlink() and BACKUP_NAME.fullmatch(path.name):
            entries.append({"filename": path.name, "size_bytes": path.stat().st_size, "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    return sorted(entries, key=lambda x: x["modified_at"], reverse=True)


def restore_backup(filename: str) -> dict:
    if not BACKUP_NAME.fullmatch(filename):
        raise ValueError("Invalid backup filename.")
    source_path = safe_backup_path(filename)
    with sqlite3.connect(source_path) as source:
        result = source.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise ValueError("The selected backup is corrupt; restore was cancelled.")
        tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "conversations" not in tables or "memories" not in tables or "settings" not in tables:
            raise ValueError("The selected file is not a valid JARVIS database snapshot.")
        with sqlite3.connect(DB_PATH) as target:
            source.backup(target)
            restored_integrity = target.execute("PRAGMA integrity_check").fetchone()
            if not restored_integrity or restored_integrity[0] != "ok":
                raise RuntimeError("Restored database failed its integrity check.")
    return {"restored": filename, "size_bytes": source_path.stat().st_size}
