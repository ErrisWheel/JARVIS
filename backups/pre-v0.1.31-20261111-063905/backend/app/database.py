import sqlite3
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


def list_memories(query: str = "", limit: int = 100):
    with connect() as db:
        if query.strip():
            terms = [term.strip() for term in query.split() if len(term.strip()) > 1][:8]
            if not terms:
                rows = db.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
            else:
                where = " OR ".join(["content LIKE ? OR category LIKE ? OR tags LIKE ?" for _ in terms])
                params = []
                for term in terms:
                    like = f"%{term}%"
                    params.extend([like, like, like])
                rows = db.execute(f"SELECT * FROM memories WHERE {where} ORDER BY updated_at DESC LIMIT ?",
                                  (*params, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def create_memory(content: str, category: str, source: str, tags: str = "") -> int:
    stamp = now_iso()
    with connect() as db:
        cur = db.execute("INSERT INTO memories(content,category,source,tags,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                         (content, category, source, tags, stamp, stamp))
        return int(cur.lastrowid)


def update_memory(memory_id: int, content: str, category: str, tags: str):
    with connect() as db:
        cur = db.execute("UPDATE memories SET content=?,category=?,tags=?,updated_at=? WHERE id=?",
                         (content, category, tags, now_iso(), memory_id))
        return cur.rowcount > 0


def delete_memory(memory_id: int):
    with connect() as db:
        cur = db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        return cur.rowcount > 0


def relevant_memories(query: str, limit: int = 6):
    # Simple lexical recall for this first slice; this is NOT vector/semantic search.
    return list_memories(query, limit)


def memory_count() -> int:
    with connect() as db:
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
