import sqlite3
import hashlib,json
from pathlib import Path

DB_PATH = Path(__file__).parent / "kami.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _migrate(conn):
    cols={r["name"] for r in conn.execute("PRAGMA table_info(context_snapshots)")}
    for name in ("prompt_tokens","reply_tokens"):
        if name not in cols:
            conn.execute(f"ALTER TABLE context_snapshots ADD COLUMN {name} INTEGER")

def init_db():
    conn = get_connection()
    try:
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()

def create_conversation() -> int:
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO conversations DEFAULT VALUES")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def add_turn(conversation_id,user_content,assistant_content,snapshot):
    conn=get_connection()
    try:
        user_id=conn.execute(
            "INSERT INTO messages (conversation_id,role,content) VALUES(?,'user',?)",
            (conversation_id,user_content)).lastrowid
        reply_id=conn.execute(
            "INSERT INTO messages (conversation_id,role,content) VALUES(?,'assistant',?)",
            (conversation_id,assistant_content)).lastrowid

        messages=[dict(m) for m in snapshot["messages"]]
        messages[-1]["id"]=user_id

        payload=json.dumps(snapshot["payload"],ensure_ascii=False,
                           sort_keys=True,separators=(",",":"))
        conn.execute(
            """INSERT INTO context_snapshots
            (conversation_id,reply_message_id,kind,system_prompt,memories,
            messages,payload,payload_hash,model,prompt_tokens,reply_tokens,options)
            VALUES(?,?,'chat',?,?,?,?,?,?,?,?,?)""",
            (conversation_id,reply_id,
             snapshot["system_prompt"],
             json.dumps(snapshot["memories"],ensure_ascii=False),
             json.dumps(messages,ensure_ascii=False),
             payload,
             hashlib.sha256(payload.encode()).hexdigest(),
             snapshot["model"],
             snapshot.get("prompt_tokens"),
             snapshot.get("reply_tokens"),
             json.dumps(snapshot["options"],ensure_ascii=False)))
        conn.commit()
        return reply_id
    finally:
        conn.close()

def get_messages(conversation_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [{"id": r["id"],"role":r["role"],"content":r["content"]} for r in rows]
    finally:
        conn.close()

def list_conversations(limit: int = 10) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.created_at,
                COUNT(m.id) AS message_count,
                (
                    SELECT first_msg.content
                    FROM messages first_msg
                    WHERE first_msg.conversation_id = c.id
                      AND first_msg.role = 'user'
                    ORDER BY first_msg.id
                    LIMIT 1
                ) AS preview
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def count_turns(conversation_id):
    conn=get_connection()
    try:
        row=conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id=? AND role='assistant'",
            (conversation_id,),
        ).fetchone()
        return row["n"]
    finally:
        conn.close()

def get_reply_id(conversation_id,turn):
    if turn<1:
        return None
    conn=get_connection()
    try:
        row=conn.execute(
            """SELECT id FROM messages
               WHERE conversation_id=? AND role='assistant'
               ORDER BY id
               LIMIT 1 OFFSET ?""",
            (conversation_id,turn-1),
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()

def get_snapshot(reply_message_id):
    conn=get_connection()
    try:
        row=conn.execute(
            "SELECT * FROM context_snapshots WHERE reply_message_id=?",
            (reply_message_id,),
        ).fetchone()
        if row is None:
            return None
        snap=dict(row)
        for key in ("memories","messages","payload","options"):
            snap[key]=json.loads(snap[key])
        return snap
    finally:
        conn.close()