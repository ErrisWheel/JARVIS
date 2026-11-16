"""Approval-gated local self-development for J.A.R.V.I.S.

The code generator may propose changes only to a small, explicit allowlist.
It cannot run shell commands, access arbitrary paths, or modify the security
boundary. Applying a proposal requires an exact confirmation phrase from the
human operator; every applied file is backed up and can be rolled back.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT, SELF_DEVELOPMENT_DIR

EDITABLE_FILES: dict[str, str] = {
    "backend/app/learning.py": "Local conversation-style learning rules (pure logic only)",
    "frontend/src/Hologram.tsx": "3D hologram visuals and interactive nodes",
    "frontend/src/styles.css": "Dashboard and hologram styling",
    "frontend/src/imageIntent.ts": "Pure local intent matching for explicit image-generation requests",
}

# These files contain the enforcement boundary, privileged routes, or approval UI.
# The self-development feature must never propose edits to them.
PROTECTED_FILES = {
    "backend/app/main.py",
    "backend/app/security.py",
    "backend/app/config.py",
    "backend/app/voice_listener.py",
    "backend/app/self_development.py",
    "backend/app/imagegen_worker.py",
    "frontend/src/App.tsx",
    "frontend/src/DevelopmentLab.tsx",
    "frontend/src/api.ts",
    "frontend/vite.config.ts",
    "scripts/Setup-JARVIS.ps1",
    "scripts/Start-JARVIS.ps1",
    "scripts/Stop-JARVIS.ps1",
    "scripts/Install-Image-Generation.ps1",
    "docs/SECURITY.md",
}

MAX_GOAL_CHARS = 1600
MAX_FILES_PER_PROPOSAL = 2
MAX_SOURCE_CHARS = 30000
MAX_OUTPUT_CHARS = 45000
MAX_FILE_BYTES = 100_000
MAX_KNOWLEDGE_ITEMS = 100
MAX_KNOWLEDGE_ITEM_CHARS = 2000
MAX_KNOWLEDGE_TOTAL_CHARS = 24000
KNOWLEDGE_FILE = SELF_DEVELOPMENT_DIR / "coding_knowledge.json"

# This is intentionally a restrictive guard for proposed executable code.
# It is not a substitute for human review or an OS-level sandbox.
_FORBIDDEN_CODE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsubprocess\b", r"\bsocket\b", r"\bctypes\b", r"\bwinreg\b",
        r"\beval\s*\(", r"\bexec\s*\(", r"\bcompile\s*\(",
        r"\b__import__\s*\(", r"\bXMLHttpRequest\b", r"\bWebSocket\s*\(",
        r"\bfetch\s*\(", r"\bchild_process\b", r"\bprocess\.env\b",
        r"\bimport\s+requests\b", r"\bfrom\s+requests\b", r"\bimport\s+httpx\b",
        r"\bfrom\s+httpx\b", r"\bimport\s+urllib\b", r"\bfrom\s+urllib\b",
        r"\bimport\s+os\b", r"\bfrom\s+os\b", r"\bimport\s+pathlib\b",
        r"\bfrom\s+pathlib\b", r"https?://",
        r"\bimport\s+subprocess\b", r"\bfrom\s+subprocess\b",
        r"\bimport\s+socket\b", r"\bfrom\s+socket\b",
        r"\bimport\s+ctypes\b", r"\bfrom\s+ctypes\b",
        r"\bimport\s*\(", r"\bnew\s+Function\s*\(",
        r"document\s*\.\s*cookie", r"localStorage", r"sessionStorage",
        r"navigator\s*\.\s*sendBeacon", r"window\s*\.\s*open",
        r"document\s*\.\s*createElement", r"insertAdjacentHTML", r"innerHTML\s*=",
        r"outerHTML\s*=", r"location\s*\.\s*(?:assign|replace)",
        r"\bWorker\s*\(", r"\bSharedWorker\s*\(", r"\bBroadcastChannel\s*\(",
    )
]


def _project_path(relative_path: str) -> Path:
    if not isinstance(relative_path, str) or "\x00" in relative_path:
        raise ValueError("Invalid project-relative path")
    if relative_path in PROTECTED_FILES or relative_path not in EDITABLE_FILES:
        raise ValueError(f"This file is protected or outside the self-development allowlist: {relative_path}")
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != relative_path:
        raise ValueError("Invalid project-relative path")
    root = ROOT.resolve(strict=True)
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError("Symbolic links are not editable")
    target = candidate.resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path resolves outside the JARVIS project") from exc
    if target != candidate.absolute() or not target.is_file():
        raise ValueError("Only existing regular source files can be edited")
    return target


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def list_editable_files() -> list[dict[str, Any]]:
    items = []
    for relative, description in EDITABLE_FILES.items():
        path = _project_path(relative)
        content = path.read_text(encoding="utf-8")
        items.append({
            "path": relative,
            "description": description,
            "size": len(content),
            "sha256": _sha256(content),
        })
    return items



def read_editable_sources(selected_files: list[str]) -> dict[str, str]:
    if not selected_files or len(selected_files) > MAX_FILES_PER_PROPOSAL:
        raise ValueError(f"Select between 1 and {MAX_FILES_PER_PROPOSAL} editable files")
    if len(set(selected_files)) != len(selected_files):
        raise ValueError("Duplicate file selections are not allowed")
    sources: dict[str, str] = {}
    total = 0
    for relative in selected_files:
        target = _project_path(relative)
        content = target.read_text(encoding="utf-8")
        total += len(content)
        sources[relative] = content
    if total > MAX_SOURCE_CHARS:
        raise ValueError("The selected source files exceed the context limit. Select fewer files.")
    return sources


def _validate_candidate(relative_path: str, content: str) -> None:
    if relative_path not in EDITABLE_FILES or relative_path in PROTECTED_FILES:
        raise ValueError(f"Attempted to modify a protected file: {relative_path}")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"The proposed content for {relative_path} is empty")
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"The proposed file is too large: {relative_path}")
    for pattern in _FORBIDDEN_CODE_PATTERNS:
        if pattern.search(content):
            raise ValueError(f"The proposed code contains a restricted capability ({pattern.pattern})")
    if relative_path.endswith((".ts", ".tsx")):
        allowed_frontend_imports = {
            "frontend/src/Hologram.tsx": {"@react-three/fiber", "@react-three/drei", "react", "three", "./api"},
            "frontend/src/imageIntent.ts": set(),
        }.get(relative_path, set())
        for source in re.findall(r"^\s*import\s+(?:type\s+)?(?:[^;]*?\s+from\s+)?['\"]([^'\"]+)['\"]", content, flags=re.MULTILINE):
            if source not in allowed_frontend_imports:
                raise ValueError(f"New or unapproved frontend dependency in {relative_path}: {source}")
    if relative_path.endswith(".py"):
        tree = ast.parse(content, filename=relative_path)
        allowed_imports = {"re", "typing", "__future__"}
        forbidden_names = {
            "open", "eval", "exec", "compile", "__import__", "globals", "locals",
            "vars", "dir", "getattr", "setattr", "delattr", "breakpoint", "input",
            "help", "memoryview", "__builtins__",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [str(node.module or "").split(".")[0]]
                if any(name not in allowed_imports for name in names):
                    raise ValueError(f"Python import outside the pure-logic allowlist in {relative_path}")
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                raise ValueError(f"Restricted Python capability in {relative_path}: {node.id}")
            if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in {"format", "format_map"}):
                raise ValueError(f"Restricted Python attribute access in {relative_path}: {node.attr}")
            if isinstance(node, (ast.Global, ast.Nonlocal, ast.ClassDef, ast.With, ast.AsyncWith)):
                raise ValueError(f"Only simple pure-logic Python functions are allowed in {relative_path}")


def _safe_self_development_root() -> Path:
    root = ROOT.resolve(strict=True)
    if SELF_DEVELOPMENT_DIR.is_symlink():
        raise ValueError("The self-development data directory cannot be a symbolic link")
    SELF_DEVELOPMENT_DIR.mkdir(parents=True, exist_ok=True)
    directory = SELF_DEVELOPMENT_DIR.resolve(strict=True)
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise ValueError("The self-development data directory resolves outside F:\\JARVIS") from exc
    return directory


def _knowledge_path() -> Path:
    directory = _safe_self_development_root()
    path = directory / KNOWLEDGE_FILE.name
    if path.is_symlink():
        raise ValueError("The coding knowledge store cannot be a symbolic link")
    return path


def list_coding_knowledge() -> list[dict[str, Any]]:
    path = _knowledge_path()
    if not path.is_file():
        return []
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("The coding knowledge store is unreadable; preserve it and inspect the JSON file") from exc
    if not isinstance(items, list):
        raise ValueError("The coding knowledge store has an invalid format")
    return [item for item in items if isinstance(item, dict) and isinstance(item.get("content"), str)]


def add_coding_knowledge(content: str, category: str = "project convention") -> dict[str, Any]:
    if not isinstance(content, str):
        raise ValueError("Coding lesson must be text")
    content = " ".join(content.split()).strip()
    category = " ".join(str(category).split()).strip()[:60] or "project convention"
    if len(content) < 8 or len(content) > MAX_KNOWLEDGE_ITEM_CHARS:
        raise ValueError(f"Coding lesson must contain 8–{MAX_KNOWLEDGE_ITEM_CHARS} characters")
    # Never persist obvious secrets as coding notes.
    secret_patterns = (
        r"(?i)\b(?:api[_ -]?key|secret[_ -]?key|password|access[_ -]?token)\s*[:=]\s*[^\s]+",
        r"(?i)\bsk-[A-Za-z0-9_-]{12,}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    )
    if any(re.search(pattern, content) for pattern in secret_patterns):
        raise ValueError("This note appears to contain a credential or private key. Remove the secret before saving.")
    items = list_coding_knowledge()
    if len(items) >= MAX_KNOWLEDGE_ITEMS:
        raise ValueError(f"The coding notebook is limited to {MAX_KNOWLEDGE_ITEMS} lessons")
    if sum(len(str(item.get("content", ""))) for item in items) + len(content) > MAX_KNOWLEDGE_TOTAL_CHARS:
        raise ValueError("The coding notebook has reached its storage limit. Remove old lessons first.")
    if any(str(item.get("content", "")).casefold() == content.casefold() for item in items):
        raise ValueError("This coding lesson is already saved")
    item = {
        "id": uuid.uuid4().hex,
        "category": category,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "operator-approved",
    }
    items.append(item)
    path = _knowledge_path()
    temp = path.with_suffix(".tmp")
    if temp.is_symlink():
        raise ValueError("A temporary coding-knowledge file cannot be a symbolic link")
    temp.unlink(missing_ok=True)
    with temp.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(items, ensure_ascii=False, indent=2))
    temp.replace(path)
    return item


def delete_coding_knowledge(item_id: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{32}", item_id or ""):
        raise ValueError("Invalid coding lesson identifier")
    items = list_coding_knowledge()
    updated = [item for item in items if item.get("id") != item_id]
    if len(updated) == len(items):
        return False
    path = _knowledge_path()
    temp = path.with_suffix(".tmp")
    if temp.is_symlink():
        raise ValueError("A temporary coding-knowledge file cannot be a symbolic link")
    temp.unlink(missing_ok=True)
    with temp.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(updated, ensure_ascii=False, indent=2))
    temp.replace(path)
    return True


def coding_knowledge_context(max_chars: int = 12000) -> list[dict[str, str]]:
    remaining = max(0, min(int(max_chars), MAX_KNOWLEDGE_TOTAL_CHARS))
    context: list[dict[str, str]] = []
    for item in reversed(list_coding_knowledge()):
        content = str(item.get("content", ""))
        if len(content) > remaining:
            continue
        context.append({"category": str(item.get("category", "project convention"))[:60], "content": content})
        remaining -= len(content)
        if remaining <= 0:
            break
    return list(reversed(context))


def _proposal_file(proposal_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", proposal_id or ""):
        raise ValueError("Invalid proposal identifier")
    development_root = _safe_self_development_root()
    directory = development_root / "proposals"
    if directory.is_symlink():
        raise ValueError("The proposal directory cannot be a symbolic link")
    directory.mkdir(parents=True, exist_ok=True)
    resolved = directory.resolve(strict=True)
    try:
        resolved.relative_to(ROOT.resolve(strict=True))
    except ValueError as exc:
        raise ValueError("The proposal directory resolves outside F:\\JARVIS") from exc
    target = resolved / f"{proposal_id}.json"
    if target.is_symlink():
        raise ValueError("A proposal record cannot be a symbolic link")
    return target


def load_proposal(proposal_id: str) -> dict[str, Any]:
    path = _proposal_file(proposal_id)
    if not path.is_file():
        raise FileNotFoundError("Proposal not found")
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if proposal.get("id") != proposal_id:
        raise ValueError("Proposal record identifier mismatch")
    return proposal


def save_proposal(proposal: dict[str, Any]) -> None:
    path = _proposal_file(str(proposal.get("id", "")))
    temp = path.with_suffix(".tmp")
    if temp.is_symlink():
        raise ValueError("A temporary proposal file cannot be a symbolic link")
    temp.unlink(missing_ok=True)
    with temp.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(proposal, ensure_ascii=False, indent=2))
    temp.replace(path)


def build_proposal_record(goal: str, selected_files: list[str], model_result: dict[str, Any]) -> dict[str, Any]:
    if not goal.strip() or len(goal) > MAX_GOAL_CHARS:
        raise ValueError(f"Describe the improvement in 1–{MAX_GOAL_CHARS} characters")
    if not selected_files or len(selected_files) > MAX_FILES_PER_PROPOSAL:
        raise ValueError(f"Select between 1 and {MAX_FILES_PER_PROPOSAL} editable files")
    if len(set(selected_files)) != len(selected_files):
        raise ValueError("Duplicate file selections are not allowed")

    requested: dict[str, tuple[str, str]] = {}
    total_source_chars = 0
    for relative in selected_files:
        target = _project_path(relative)
        original = target.read_text(encoding="utf-8")
        total_source_chars += len(original)
        requested[relative] = (original, _sha256(original))
    if total_source_chars > MAX_SOURCE_CHARS:
        raise ValueError("The selected source files exceed the self-development context limit. Select fewer files.")

    changes_raw = model_result.get("changes")
    if not isinstance(changes_raw, list) or not changes_raw:
        raise ValueError("The local model did not return any file changes")
    if len(changes_raw) > len(requested):
        raise ValueError("The local model returned more changed files than were selected")

    changes = []
    seen = set()
    total_output_chars = 0
    for item in changes_raw:
        if not isinstance(item, dict):
            raise ValueError("Malformed change entry from the local model")
        relative = str(item.get("path", ""))
        if relative not in requested or relative in seen:
            raise ValueError(f"The model tried to change an unselected or duplicate file: {relative}")
        seen.add(relative)
        new_content = item.get("content")
        if not isinstance(new_content, str):
            raise ValueError(f"Missing complete file content for {relative}")
        _validate_candidate(relative, new_content)
        original, old_hash = requested[relative]
        total_output_chars += len(new_content)
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), new_content.splitlines(keepends=True),
            fromfile=f"a/{relative}", tofile=f"b/{relative}", n=3,
        ))
        changes.append({
            "path": relative,
            "reason": str(item.get("reason", "Proposed improvement"))[:500],
            "old_sha256": old_hash,
            "new_sha256": _sha256(new_content),
            "old_content": original,
            "new_content": new_content,
            "diff": diff[:30000],
        })
    if total_output_chars > MAX_OUTPUT_CHARS:
        raise ValueError("The model's proposed changes are too large to review safely")

    proposal_id = uuid.uuid4().hex
    return {
        "id": proposal_id,
        "goal": goal.strip(),
        "summary": str(model_result.get("summary", "Proposed code improvement"))[:1000],
        "warnings": [str(value)[:300] for value in model_result.get("warnings", [])[:5]] if isinstance(model_result.get("warnings", []), list) else [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "changes": changes,
    }


def apply_proposal(proposal_id: str, confirmation: str) -> dict[str, Any]:
    required = f"APPLY:{proposal_id}"
    if confirmation != required:
        raise PermissionError(f"Explicit approval required. Type {required} exactly.")
    proposal = load_proposal(proposal_id)
    if proposal.get("status") != "pending":
        raise ValueError("Only a pending proposal can be applied")
    development_root = _safe_self_development_root()
    backup_parent = development_root / "backups"
    if backup_parent.is_symlink():
        raise ValueError("The self-development backup directory cannot be a symbolic link")
    backup_root = backup_parent / proposal_id
    if backup_root.is_symlink():
        raise ValueError("The proposal backup directory cannot be a symbolic link")
    written: list[str] = []
    # Validate all targets and source hashes before writing any file.
    targets = []
    for change in proposal["changes"]:
        target = _project_path(change["path"])
        current = target.read_text(encoding="utf-8")
        if _sha256(current) != change["old_sha256"]:
            raise RuntimeError(f"Source changed since the proposal was created: {change['path']}. Generate a fresh proposal.")
        _validate_candidate(change["path"], change["new_content"])
        targets.append((target, change))

    try:
        for target, change in targets:
            backup = backup_root / change["path"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            temp = target.with_name(target.name + f".{proposal_id}.jarvis-tmp")
            temp.write_text(change["new_content"], encoding="utf-8")
            temp.replace(target)
            written.append(change["path"])
    except Exception:
        # Restore every target already replaced, preserving all-or-nothing behavior.
        for target, change in targets:
            if change["path"] in written:
                backup = backup_root / change["path"]
                if backup.is_file():
                    backup.replace(target)
        raise

    proposal["status"] = "applied"
    proposal["applied_at"] = datetime.now(timezone.utc).isoformat()
    save_proposal(proposal)
    return {"ok": True, "proposal_id": proposal_id, "status": "applied", "files": written,
            "backup_directory": str(backup_root)}


def rollback_proposal(proposal_id: str, confirmation: str) -> dict[str, Any]:
    required = f"RESTORE:{proposal_id}"
    if confirmation != required:
        raise PermissionError(f"Explicit rollback approval required. Type {required} exactly.")
    proposal = load_proposal(proposal_id)
    if proposal.get("status") != "applied":
        raise ValueError("Only an applied proposal can be rolled back")
    development_root = _safe_self_development_root()
    backup_parent = development_root / "backups"
    backup_root = backup_parent / proposal_id
    if backup_parent.is_symlink() or backup_root.is_symlink():
        raise ValueError("The self-development backup directory cannot be a symbolic link")
    try:
        backup_root.resolve(strict=True).relative_to(ROOT.resolve(strict=True))
    except ValueError as exc:
        raise ValueError("The proposal backup directory resolves outside F:\\JARVIS") from exc
    restored = []
    targets = []
    for change in proposal["changes"]:
        target = _project_path(change["path"])
        backup = backup_root / change["path"]
        if not backup.is_file():
            raise FileNotFoundError(f"Backup is missing for {change['path']}")
        current = target.read_text(encoding="utf-8")
        if _sha256(current) != change["new_sha256"]:
            raise RuntimeError(f"{change['path']} has changed since application; refusing to overwrite newer work")
        targets.append((target, backup))
    for target, backup in targets:
        temp = target.with_name(target.name + f".{proposal_id}.rollback-tmp")
        temp.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        temp.replace(target)
        restored.append(str(target.relative_to(ROOT.resolve(strict=True))).replace("\\", "/"))
    proposal["status"] = "rolled_back"
    proposal["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    save_proposal(proposal)
    return {"ok": True, "proposal_id": proposal_id, "status": "rolled_back", "files": restored}
