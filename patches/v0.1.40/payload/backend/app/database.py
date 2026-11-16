import sqlite3
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DB_PATH, DATA_DIR


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'assistant',
            created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_conversation_id ON conversations(conversation_id, id)")
        db.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            source TEXT NOT NULL DEFAULT 'user-confirmed',
            tags TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        memory_columns = {row[1] for row in db.execute("PRAGMA table_info(memories)")}
        if "workspace_id" not in memory_columns:
            # Existing memories migrate into the Personal workspace without
            # changing their content, IDs, FTS rows, or timestamps.
            db.execute("ALTER TABLE memories ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default'")
        # SQLite FTS5 is built into the standard SQLite library on supported Python
        # builds. Keep a graceful lexical fallback for builds compiled without FTS5.
        try:
            fts_exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='memories_fts'"
            ).fetchone() is not None
            db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5("
                "content, category, tags, content='memories', content_rowid='id')"
            )
            if not fts_exists:
                db.execute(
                    "INSERT INTO memories_fts(rowid,content,category,tags) "
                    "SELECT id,content,category,tags FROM memories"
                )
            db.executescript("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid,content,category,tags)
                    VALUES(new.id,new.content,new.category,new.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts,rowid,content,category,tags)
                    VALUES('delete',old.id,old.content,old.category,old.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts,rowid,content,category,tags)
                    VALUES('delete',old.id,old.content,old.category,old.tags);
                    INSERT INTO memories_fts(rowid,content,category,tags)
                    VALUES(new.id,new.content,new.category,new.tags);
                END;
            """)
        except sqlite3.OperationalError:
            # Older/custom SQLite builds may omit FTS5. The Python ranker below remains local.
            pass
        db.execute("""CREATE TABLE IF NOT EXISTS operator_instructions (
            category TEXT PRIMARY KEY,
            instruction TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'explicit-operator-correction',
            updated_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS conversation_state (
            conversation_id TEXT PRIMARY KEY,
            last_user_request TEXT NOT NULL DEFAULT '',
            last_assistant_tail TEXT NOT NULL DEFAULT '',
            last_user_code_anchor TEXT NOT NULL DEFAULT '',
            task_kind TEXT NOT NULL DEFAULT 'conversation',
            updated_at TEXT NOT NULL
        )""")
        db.execute(
            "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)",
            ("style_learning_enabled", "1", now_iso()),
        )
        db.execute(
            "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)",
            ("style_profile", "{}", now_iso()),
        )
        # Seed only once from the operator's explicitly supplied prior corrections.
        # The marker prevents deleted defaults from silently returning on later startups.
        seeded = db.execute("SELECT value FROM settings WHERE key='operator_defaults_seeded'").fetchone()
        if not seeded:
            stamp = now_iso()
            db.execute(
                "INSERT OR IGNORE INTO operator_instructions(category,instruction,source,updated_at) VALUES(?,?,?,?)",
                ("emoji", "Never use emojis in replies.", "operator-confirmed-from-prior-correction", stamp),
            )
            db.execute(
                "INSERT OR IGNORE INTO operator_instructions(category,instruction,source,updated_at) VALUES(?,?,?,?)",
                ("humor", "Do not make jokes or playful banter unless the operator explicitly invites it.", "operator-confirmed-from-prior-correction", stamp),
            )
            db.execute(
                "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)",
                ("operator_defaults_seeded", "1", stamp),
            )
        db.commit()


@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def add_message(conversation_id: str, role: str, content: str, mode: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO conversations(conversation_id,role,content,mode,created_at) VALUES(?,?,?,?,?)",
                   (conversation_id, role, content, mode, now_iso()))


def recent_messages(conversation_id: str, limit: int = 20):
    with connect() as db:
        rows = db.execute("SELECT role,content FROM conversations WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                          (conversation_id, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]


_MEMORY_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "what", "when", "where",
    "which", "who", "why", "how", "are", "was", "were", "have", "has", "had",
    "you", "your", "our", "their", "them", "they", "she", "him", "her", "his",
    "about", "into", "onto", "then", "than", "also", "just", "please", "could",
    "would", "should", "can", "does", "did", "not", "but", "its", "it's", "a", "an", "of", "to", "in", "on", "is", "it",
}


def _memory_query_tokens(query: str) -> list[str]:
    tokens = [token.casefold() for token in re.findall(r"[\w'-]{2,}", str(query or ""), flags=re.UNICODE)]
    return list(dict.fromkeys(token for token in tokens if token not in _MEMORY_STOPWORDS))[:16]


def _fallback_rank_memories(rows, tokens: list[str], query: str, limit: int) -> list[dict]:
    phrase = str(query or "").casefold().strip()
    ranked: list[tuple[float, dict]] = []
    for row in rows:
        item = dict(row)
        content = str(item.get("content", "")).casefold()
        category = str(item.get("category", "")).casefold()
        tags = str(item.get("tags", "")).casefold()
        score = 0.0
        if phrase and len(phrase) > 3 and phrase in content:
            score += 5.0
        for token in tokens:
            if token in content:
                score += 2.0 + min(content.count(token), 3) * 0.25
            if token in tags:
                score += 1.8
            if token in category:
                score += 1.2
        if score > 0:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (pair[0], pair[1].get("updated_at", "")), reverse=True)
    return [item for _, item in ranked[:limit]]


def _search_memory_rows(db: sqlite3.Connection, query: str, limit: int, workspace_id: str | None = None):
    tokens = _memory_query_tokens(query)
    scope_sql = " AND (m.workspace_id=? OR m.workspace_id IS NULL)" if workspace_id else ""
    if not tokens:
        if workspace_id:
            return db.execute("SELECT * FROM memories m WHERE m.workspace_id=? OR m.workspace_id IS NULL ORDER BY m.updated_at DESC LIMIT ?", (workspace_id, limit)).fetchall()
        return db.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()

    # Quote each term so user input is data, never raw FTS query syntax.
    match = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
    try:
        return db.execute(
            "SELECT m.* FROM memories_fts f JOIN memories m ON m.id=f.rowid "
            "WHERE memories_fts MATCH ?" + scope_sql +
            " ORDER BY bm25(memories_fts, 3.0, 1.4, 2.0), m.updated_at DESC LIMIT ?",
            (match, workspace_id, limit) if workspace_id else (match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        all_rows = db.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT 5000").fetchall()
        if workspace_id:
            all_rows = [row for row in all_rows if row["workspace_id"] == workspace_id or row["workspace_id"] is None]
        return _fallback_rank_memories(all_rows, tokens, query, limit)


def list_memories(query: str = "", limit: int = 100, workspace_id: str | None = None):
    with connect() as db:
        if query.strip():
            rows = _search_memory_rows(db, query, limit, workspace_id)
        elif workspace_id:
            rows = db.execute("SELECT * FROM memories WHERE workspace_id=? OR workspace_id IS NULL ORDER BY updated_at DESC LIMIT ?", (workspace_id, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def create_memory(content: str, category: str, source: str, tags: str = "", workspace_id: str = "default") -> int:
    stamp = now_iso()
    with connect() as db:
        cur = db.execute("INSERT INTO memories(content,category,source,tags,workspace_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                         (content, category, source, tags, workspace_id or "default", stamp, stamp))
        return int(cur.lastrowid)


def update_memory(memory_id: int, content: str, category: str, tags: str):
    with connect() as db:
        cur = db.execute("UPDATE memories SET content=?,category=?,tags=?,updated_at=? WHERE id=?",
                         (content, category, tags, now_iso(), memory_id))
        changed = cur.rowcount > 0
    if changed:
        # The old embedding no longer represents the edited memory.
        from .platform_store import delete_memory_vectors
        delete_memory_vectors(memory_id)
    return changed


def delete_memory(memory_id: int):
    with connect() as db:
        cur = db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        changed = cur.rowcount > 0
    if changed:
        from .platform_store import delete_memory_vectors
        delete_memory_vectors(memory_id)
    return changed


def relevant_memories(query: str, limit: int = 6, workspace_id: str | None = None):
    """Retrieve locally indexed memory using SQLite FTS5 BM25 with a safe fallback."""
    if not str(query or "").strip():
        return []
    with connect() as db:
        rows = _search_memory_rows(db, query, max(1, min(int(limit), 20)), workspace_id)
    return [dict(row) for row in rows]


def memory_count(workspace_id: str | None = None) -> int:
    with connect() as db:
        if workspace_id:
            return int(db.execute("SELECT COUNT(*) FROM memories WHERE workspace_id=? OR workspace_id IS NULL", (workspace_id,)).fetchone()[0])
        return int(db.execute("SELECT COUNT(*) FROM memories").fetchone()[0])


def get_setting(key: str, default: str = "") -> str:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, now_iso()),
        )


def set_operator_instruction(category: str, instruction: str, source: str = "explicit-operator-correction") -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO operator_instructions(category,instruction,source,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(category) DO UPDATE SET instruction=excluded.instruction, source=excluded.source, updated_at=excluded.updated_at",
            (category, instruction, source, now_iso()),
        )


def get_operator_instructions() -> list[dict]:
    try:
        with connect() as db:
            rows = db.execute("SELECT category,instruction,source,updated_at FROM operator_instructions ORDER BY category").fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        # The API startup migration creates this table; this fallback keeps utility tests safe.
        return []


def delete_operator_instruction(category: str) -> bool:
    with connect() as db:
        cur = db.execute("DELETE FROM operator_instructions WHERE category=?", (category,))
        return cur.rowcount > 0


def get_conversation_state(conversation_id: str) -> dict:
    try:
        with connect() as db:
            row = db.execute(
                "SELECT conversation_id,last_user_request,last_assistant_tail,last_user_code_anchor,task_kind,updated_at "
                "FROM conversation_state WHERE conversation_id=?", (conversation_id,)
            ).fetchone()
        return dict(row) if row else {}
    except sqlite3.OperationalError:
        return {}


def update_conversation_state(
    conversation_id: str, last_user_request: str, last_assistant_answer: str,
    last_user_code_anchor: str | None = None, task_kind: str = "conversation",
) -> None:
    stamp = now_iso()
    with connect() as db:
        existing = db.execute(
            "SELECT last_user_code_anchor FROM conversation_state WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        anchor = (str(existing["last_user_code_anchor"]) if existing else "") if last_user_code_anchor is None else last_user_code_anchor
        db.execute(
            "INSERT INTO conversation_state(conversation_id,last_user_request,last_assistant_tail,last_user_code_anchor,task_kind,updated_at) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET "
            "last_user_request=excluded.last_user_request,last_assistant_tail=excluded.last_assistant_tail,"
            "last_user_code_anchor=excluded.last_user_code_anchor,task_kind=excluded.task_kind,updated_at=excluded.updated_at",
            (conversation_id, last_user_request[-4000:], last_assistant_answer[-2500:], anchor[-5000:], task_kind, stamp),
        )
