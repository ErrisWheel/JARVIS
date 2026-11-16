"""Persistent local workspace, activity, task, permission, and capability metadata.

This module stores metadata only. It never executes extension code or shell commands.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DB_PATH, DATA_DIR, ROOT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_platform_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversation_meta (
            conversation_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL DEFAULT 'New conversation',
            pinned INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
        );
        CREATE INDEX IF NOT EXISTS idx_conversation_meta_workspace ON conversation_meta(workspace_id, archived, pinned, updated_at);
        CREATE TABLE IF NOT EXISTS activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL DEFAULT 'main',
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_activity_events_conversation ON activity_events(conversation_id, id DESC);
        CREATE TABLE IF NOT EXISTS task_jobs (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL DEFAULT 'main',
            goal TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            results_json TEXT NOT NULL DEFAULT '[]',
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_task_jobs_updated ON task_jobs(updated_at DESC);
        CREATE TABLE IF NOT EXISTS tool_permissions (
            capability TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL,
            requires_approval INTEGER NOT NULL,
            description TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_embeddings (
            memory_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(memory_id, model)
        );
        CREATE TABLE IF NOT EXISTS memory_links (
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            similarity REAL NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(source_id,target_id,model),
            CHECK(source_id <> target_id)
        );
        CREATE INDEX IF NOT EXISTS idx_memory_links_source ON memory_links(source_id,model,similarity DESC);
        """)
        stamp = _now()
        db.execute("INSERT OR IGNORE INTO workspaces(id,name,created_at,updated_at) VALUES('default','Personal',?,?)", (stamp, stamp))
        db.execute("INSERT OR IGNORE INTO conversation_meta(conversation_id,workspace_id,title,created_at,updated_at) VALUES('main','default','Main conversation',?,?)", (stamp, stamp))
        # Migrate conversations created before the workspace manager existed.
        # This makes the operator's existing chat history discoverable without
        # moving or rewriting the underlying conversation messages.
        db.execute("""
            INSERT OR IGNORE INTO conversation_meta(conversation_id,workspace_id,title,created_at,updated_at)
            SELECT c.conversation_id, 'default',
                   COALESCE((SELECT substr(trim(u.content),1,72) FROM conversations u
                             WHERE u.conversation_id=c.conversation_id AND u.role='user'
                             ORDER BY u.id ASC LIMIT 1), 'Conversation ' || substr(c.conversation_id,1,8)),
                   COALESCE(MIN(c.created_at), ?), COALESCE(MAX(c.created_at), ?)
            FROM conversations c
            WHERE c.conversation_id IS NOT NULL AND trim(c.conversation_id) <> ''
            GROUP BY c.conversation_id
        """, (stamp, stamp))
        defaults = [
            ('local_chat', 1, 0, 'Use the local language model for chat, explanations, and supervised task plans'),
            ('memory_search', 1, 0, 'Search and retrieve local saved memories'),
            ('document_search', 1, 0, 'Read operator-selected files in imports'),
            ('image_generation', 1, 1, 'Generate an image using the local image model'),
            ('image_analysis', 1, 0, 'Analyze an operator-selected generated image with the local vision model'),
            ('code_proposal', 1, 0, 'Propose source changes for operator review'),
            ('code_apply', 1, 1, 'Apply a reviewed source proposal after exact confirmation'),
            ('filesystem_imports', 1, 0, 'Read files inside the JARVIS imports folder'),
            ('voice_input', 1, 0, 'Use the installed local microphone and Whisper voice input'),
            ('voice_output', 1, 0, 'Generate speech with the installed local Kokoro voice engine'),
            ('image_analysis', 1, 0, 'Analyze generated images with the installed local vision model'),
            ('external_network', 0, 1, 'External internet and remote services; disabled by default'),
            ('shell_execution', 0, 1, 'Arbitrary shell execution; disabled and unsupported'),
        ]
        for capability, enabled, approval, description in defaults:
            db.execute(
                "INSERT OR IGNORE INTO tool_permissions(capability,enabled,requires_approval,description,updated_at) VALUES(?,?,?,?,?)",
                (capability, enabled, approval, description, stamp),
            )
        db.execute("UPDATE tool_permissions SET description=? WHERE capability='local_chat'", ("Use the local language model for chat, explanations, and supervised task plans",))
        # Recover orphaned active jobs as resumable interruptions; never auto-run after restart.
        db.execute("UPDATE task_jobs SET status='interrupted', error='Backend restarted before this task completed. Review and resume it manually.', updated_at=? WHERE status='running'", (stamp,))
        db.commit()


def new_id(prefix: str = "") -> str:
    return (prefix + secrets.token_hex(12))[:80]


def create_workspace(name: str) -> dict:
    stamp = _now(); workspace_id = new_id("ws_")
    with _connect() as db:
        db.execute("INSERT INTO workspaces(id,name,created_at,updated_at) VALUES(?,?,?,?)", (workspace_id, name.strip()[:64], stamp, stamp))
    return get_workspace(workspace_id) or {}


def get_workspace(workspace_id: str) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
    return dict(row) if row else None


def list_workspaces(include_archived: bool = False) -> list[dict]:
    with _connect() as db:
        rows = db.execute("SELECT w.*, (SELECT COUNT(*) FROM conversation_meta c WHERE c.workspace_id=w.id AND c.archived=0) AS conversation_count FROM workspaces w WHERE (?=1 OR w.archived=0) ORDER BY w.created_at", (int(include_archived),)).fetchall()
    return [dict(r) for r in rows]


def update_workspace(workspace_id: str, name: str | None = None, archived: bool | None = None) -> bool:
    fields: list[str] = []; values: list[Any] = []
    if name is not None: fields.append("name=?"); values.append(name.strip()[:64])
    if archived is not None: fields.append("archived=?"); values.append(int(archived))
    if not fields: return get_workspace(workspace_id) is not None
    fields.append("updated_at=?"); values.append(_now()); values.append(workspace_id)
    with _connect() as db:
        cur = db.execute(f"UPDATE workspaces SET {','.join(fields)} WHERE id=?", values)
    return cur.rowcount > 0


def ensure_conversation(conversation_id: str, workspace_id: str = "default", title: str | None = None) -> None:
    stamp = _now()
    with _connect() as db:
        exists = db.execute("SELECT id FROM workspaces WHERE id=? AND archived=0", (workspace_id,)).fetchone()
        if not exists: workspace_id = "default"
        db.execute(
            "INSERT OR IGNORE INTO conversation_meta(conversation_id,workspace_id,title,created_at,updated_at) VALUES(?,?,?,?,?)",
            (conversation_id, workspace_id, (title or "New conversation")[:100], stamp, stamp),
        )


def create_conversation(workspace_id: str, title: str = "New conversation") -> dict:
    if not get_workspace(workspace_id) or get_workspace(workspace_id).get("archived"):
        raise ValueError("Workspace not found or archived")
    cid = new_id("chat_"); stamp = _now()
    with _connect() as db:
        db.execute("INSERT INTO conversation_meta(conversation_id,workspace_id,title,created_at,updated_at) VALUES(?,?,?,?,?)", (cid, workspace_id, title.strip()[:100] or "New conversation", stamp, stamp))
    return get_conversation_meta(cid) or {}


def get_conversation_meta(conversation_id: str) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM conversation_meta WHERE conversation_id=?", (conversation_id,)).fetchone()
    return dict(row) if row else None




def conversation_workspace_id(conversation_id: str) -> str:
    """Resolve a chat's memory scope, preserving legacy chats in Personal."""
    meta = get_conversation_meta(str(conversation_id or "main")[:80])
    workspace_id = str((meta or {}).get("workspace_id") or "default")
    workspace = get_workspace(workspace_id)
    return workspace_id if workspace else "default"

def list_conversations(workspace_id: str | None = None, query: str = "", include_archived: bool = False) -> list[dict]:
    sql = "SELECT m.*, (SELECT COUNT(*) FROM conversations c WHERE c.conversation_id=m.conversation_id) AS message_count FROM conversation_meta m WHERE (? IS NULL OR m.workspace_id=?) AND (?=1 OR m.archived=0)"
    params: list[Any] = [workspace_id, workspace_id, int(include_archived)]
    if query.strip():
        sql += " AND (m.title LIKE ? OR EXISTS (SELECT 1 FROM conversations c WHERE c.conversation_id=m.conversation_id AND c.content LIKE ?))"
        q = f"%{query.strip()[:120]}%"; params.extend([q, q])
    sql += " ORDER BY m.pinned DESC, m.updated_at DESC LIMIT 200"
    with _connect() as db: rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_conversation_meta(conversation_id: str, *, title: str | None = None, pinned: bool | None = None, archived: bool | None = None, workspace_id: str | None = None) -> bool:
    fields: list[str] = []; values: list[Any] = []
    if title is not None: fields.append("title=?"); values.append(title.strip()[:100] or "New conversation")
    if pinned is not None: fields.append("pinned=?"); values.append(int(pinned))
    if archived is not None: fields.append("archived=?"); values.append(int(archived))
    if workspace_id is not None:
        target_workspace = get_workspace(workspace_id)
        if not target_workspace or target_workspace.get("archived"): return False
        fields.append("workspace_id=?"); values.append(workspace_id)
    if not fields: return get_conversation_meta(conversation_id) is not None
    fields.append("updated_at=?"); values.append(_now()); values.append(conversation_id)
    with _connect() as db: cur = db.execute(f"UPDATE conversation_meta SET {','.join(fields)} WHERE conversation_id=?", values)
    return cur.rowcount > 0


def touch_conversation(conversation_id: str) -> None:
    ensure_conversation(conversation_id)
    stamp = _now()
    with _connect() as db:
        meta = db.execute("SELECT title FROM conversation_meta WHERE conversation_id=?", (conversation_id,)).fetchone()
        title = str(meta["title"] or "") if meta else ""
        # Auto-title only untouched new conversations. A manually renamed title
        # is never overwritten by later messages.
        if conversation_id != "main" and title in {"New conversation", "Conversation"}:
            first_user = db.execute("SELECT content FROM conversations WHERE conversation_id=? AND role='user' ORDER BY id ASC LIMIT 1", (conversation_id,)).fetchone()
            if first_user and str(first_user["content"]).strip():
                candidate = re.sub(r"\s+", " ", str(first_user["content"])).strip()
                db.execute("UPDATE conversation_meta SET title=?,updated_at=? WHERE conversation_id=?", (candidate[:96] + ("…" if len(candidate) > 96 else ""), stamp, conversation_id))
                return
        db.execute("UPDATE conversation_meta SET updated_at=? WHERE conversation_id=?", (stamp, conversation_id))


def record_event(conversation_id: str, event_type: str, title: str, payload: dict | None = None) -> int:
    safe_payload = json.dumps(payload or {}, ensure_ascii=False)[:12000]
    safe_conversation = conversation_id[:80] or "main"
    try:
        with _connect() as db:
            cur = db.execute("INSERT INTO activity_events(conversation_id,event_type,title,payload,created_at) VALUES(?,?,?,?,?)", (safe_conversation, event_type[:80], title[:160], safe_payload, _now()))
            # Keep the most recent 2,000 events per conversation. SQLite IDs remain
            # monotonic, while replay stays bounded and predictable.
            db.execute("DELETE FROM activity_events WHERE conversation_id=? AND id NOT IN (SELECT id FROM activity_events WHERE conversation_id=? ORDER BY id DESC LIMIT 2000)", (safe_conversation, safe_conversation))
            return int(cur.lastrowid)
    except sqlite3.OperationalError as exc:
        if "no such table: activity_events" not in str(exc).lower():
            raise
        # Direct local function invocation may happen outside FastAPI lifespan.
        from .database import init_db
        init_db()
        init_platform_store()
        with _connect() as db:
            cur = db.execute("INSERT INTO activity_events(conversation_id,event_type,title,payload,created_at) VALUES(?,?,?,?,?)", (safe_conversation, event_type[:80], title[:160], safe_payload, _now()))
            db.execute("DELETE FROM activity_events WHERE conversation_id=? AND id NOT IN (SELECT id FROM activity_events WHERE conversation_id=? ORDER BY id DESC LIMIT 2000)", (safe_conversation, safe_conversation))
            return int(cur.lastrowid)


def list_events(conversation_id: str = "main", limit: int = 100) -> list[dict]:
    with _connect() as db:
        rows = db.execute("SELECT * FROM activity_events WHERE conversation_id=? ORDER BY id DESC LIMIT ?", (conversation_id[:80], max(1, min(int(limit), 500)))).fetchall()
    result = []
    for row in reversed(rows):
        item = dict(row)
        try: item["payload"] = json.loads(item["payload"])
        except (TypeError, ValueError): item["payload"] = {}
        result.append(item)
    return result


def create_task(task_id: str, conversation_id: str, goal: str, model: str, plan: list[dict]) -> dict:
    stamp = _now()
    with _connect() as db:
        db.execute("INSERT INTO task_jobs(id,conversation_id,goal,model,status,plan_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (task_id, conversation_id, goal[:4000], model[:120], "planned", json.dumps(plan, ensure_ascii=False), stamp, stamp))
    return get_task(task_id) or {}


def get_task(task_id: str) -> dict | None:
    with _connect() as db: row = db.execute("SELECT * FROM task_jobs WHERE id=?", (task_id,)).fetchone()
    if not row: return None
    item = dict(row)
    for field in ("plan_json", "results_json"):
        try: item[field.removesuffix("_json")] = json.loads(item[field])
        except (TypeError, ValueError): item[field.removesuffix("_json")] = []
        del item[field]
    return item


def list_tasks(limit: int = 50) -> list[dict]:
    with _connect() as db: rows = db.execute("SELECT id FROM task_jobs ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    return [task for row in rows if (task := get_task(row["id"]))]


def update_task(task_id: str, *, status: str | None = None, plan: list[dict] | None = None, results: list[dict] | None = None, error: str | None = None, started: bool = False, completed: bool = False) -> bool:
    fields: list[str] = ["updated_at=?"]; values: list[Any] = [_now()]
    if status is not None: fields.append("status=?"); values.append(status)
    if plan is not None: fields.append("plan_json=?"); values.append(json.dumps(plan, ensure_ascii=False))
    if results is not None: fields.append("results_json=?"); values.append(json.dumps(results, ensure_ascii=False))
    if error is not None: fields.append("error=?"); values.append(error[:4000])
    if started: fields.append("started_at=?"); values.append(_now())
    if completed: fields.append("completed_at=?"); values.append(_now())
    values.append(task_id)
    with _connect() as db: cur = db.execute(f"UPDATE task_jobs SET {','.join(fields)} WHERE id=?", values)
    return cur.rowcount > 0


def list_permissions() -> list[dict]:
    with _connect() as db: rows = db.execute("SELECT * FROM tool_permissions ORDER BY capability").fetchall()
    return [dict(r) for r in rows]


def set_permission(capability: str, enabled: bool, requires_approval: bool | None = None) -> bool:
    with _connect() as db:
        row = db.execute("SELECT requires_approval FROM tool_permissions WHERE capability=?", (capability,)).fetchone()
        if not row: return False
        approval = int(bool(row["requires_approval"])) if requires_approval is None else int(requires_approval)
        db.execute("UPDATE tool_permissions SET enabled=?,requires_approval=?,updated_at=? WHERE capability=?", (int(enabled), approval, _now(), capability))
    return True


def memory_vector_upsert(memory_id: int, model: str, vector: list[float]) -> None:
    with _connect() as db:
        db.execute("INSERT INTO memory_embeddings(memory_id,model,dimensions,vector_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(memory_id,model) DO UPDATE SET dimensions=excluded.dimensions,vector_json=excluded.vector_json,updated_at=excluded.updated_at", (memory_id, model, len(vector), json.dumps(vector), _now()))


def get_memory_vectors(model: str, workspace_id: str | None = None) -> list[dict]:
    if workspace_id:
        sql = "SELECT e.memory_id,e.vector_json,m.content,m.category,m.tags,m.updated_at,m.workspace_id FROM memory_embeddings e JOIN memories m ON m.id=e.memory_id WHERE e.model=? AND (m.workspace_id=? OR m.workspace_id IS NULL)"
        params = (model, workspace_id)
    else:
        sql = "SELECT e.memory_id,e.vector_json,m.content,m.category,m.tags,m.updated_at,m.workspace_id FROM memory_embeddings e JOIN memories m ON m.id=e.memory_id WHERE e.model=?"
        params = (model,)
    with _connect() as db: rows = db.execute(sql, params).fetchall()
    output=[]
    for r in rows:
        item=dict(r)
        try: item["vector"] = json.loads(item.pop("vector_json"))
        except (TypeError,ValueError): continue
        output.append(item)
    return output


def list_skill_manifests() -> list[dict]:
    """Read-only declarative skills; no Python/JS in a manifest is ever executed."""
    root = (ROOT / "skills").resolve()
    if root.exists() and (root.is_symlink() or not root.is_dir()): return []
    root.mkdir(parents=True, exist_ok=True)
    result=[]
    for path in root.glob("*/manifest.json"):
        try:
            if path.is_symlink() or path.resolve().parent.parent != root: continue
            data=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data,dict): continue
            name=str(data.get("name", "")).strip()[:80]
            skill_id=str(data.get("id", path.parent.name)).strip()[:80]
            description=str(data.get("description", "")).strip()[:300]
            prompt_template=str(data.get("prompt_template", "")).strip()[:3000]
            capabilities=data.get("capabilities", [])
            if not name or not skill_id or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,79}", skill_id) or not isinstance(capabilities,list): continue
            safe_caps=[str(x)[:80] for x in capabilities if str(x) in {"local_chat","memory_search","document_search","image_generation","code_proposal"}]
            result.append({"id":skill_id,"name":name,"description":description,"capabilities":safe_caps,"prompt_template":prompt_template,"source":"manifest"})
        except (OSError,ValueError,TypeError):
            continue
    return sorted(result,key=lambda x:x["name"].casefold())


def delete_memory_vectors(memory_id: int) -> None:
    try:
        with _connect() as db:
            db.execute("DELETE FROM memory_embeddings WHERE memory_id=?", (int(memory_id),))
            db.execute("DELETE FROM memory_links WHERE source_id=? OR target_id=?", (int(memory_id), int(memory_id)))
    except sqlite3.OperationalError as exc:
        # The semantic subsystem is optional and may not have been initialized
        # for a standalone database.py caller. There can be no stale vectors yet.
        if "no such table" not in str(exc).lower():
            raise


def delete_all_memory_vectors(model: str | None = None) -> int:
    with _connect() as db:
        if model:
            cur = db.execute("DELETE FROM memory_embeddings WHERE model=?", (model,))
            db.execute("DELETE FROM memory_links WHERE model=?", (model,))
        else:
            cur = db.execute("DELETE FROM memory_embeddings")
            db.execute("DELETE FROM memory_links")
        return int(cur.rowcount)


def replace_memory_links(model: str, edges: list[tuple[int, int, float]]) -> int:
    """Replace the bounded local semantic graph for one embedding model."""
    stamp = _now()
    safe_edges = [(int(a), int(b), model[:120], max(-1.0, min(1.0, float(score))), stamp)
                  for a, b, score in edges if int(a) != int(b) and math_is_finite(score)]
    with _connect() as db:
        db.execute("DELETE FROM memory_links WHERE model=?", (model[:120],))
        db.executemany(
            "INSERT OR REPLACE INTO memory_links(source_id,target_id,model,similarity,updated_at) VALUES(?,?,?,?,?)",
            safe_edges,
        )
    return len(safe_edges)


def list_memory_graph(model: str, limit: int = 250, workspace_id: str | None = None) -> dict:
    bounded = max(1, min(int(limit), 400))
    scope_sql = " AND (m.workspace_id=? OR m.workspace_id IS NULL)" if workspace_id else ""
    params = (model[:120], workspace_id, bounded) if workspace_id else (model[:120], bounded)
    with _connect() as db:
        node_rows = db.execute(
            "SELECT DISTINCT m.id,m.content,m.category,m.tags,m.updated_at FROM memories m "
            "JOIN memory_embeddings e ON e.memory_id=m.id WHERE e.model=?" + scope_sql +
            " ORDER BY m.updated_at DESC LIMIT ?", params,
        ).fetchall()
        node_ids = [int(row["id"]) for row in node_rows]
        if not node_ids:
            return {"nodes": [], "edges": [], "model": model}
        placeholders = ",".join("?" for _ in node_ids)
        edge_rows = db.execute(
            f"SELECT source_id,target_id,similarity FROM memory_links WHERE model=? "
            f"AND source_id IN ({placeholders}) AND target_id IN ({placeholders}) ORDER BY similarity DESC LIMIT 2000",
            [model[:120], *node_ids, *node_ids],
        ).fetchall()
    return {
        "model": model,
        "nodes": [{"id": int(row["id"]), "label": str(row["content"])[:180], "category": row["category"], "tags": row["tags"], "updated_at": row["updated_at"]} for row in node_rows],
        "edges": [{"source": int(row["source_id"]), "target": int(row["target_id"]), "similarity": round(float(row["similarity"]), 4)} for row in edge_rows],
    }


def math_is_finite(value: Any) -> bool:
    try:
        import math
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False
