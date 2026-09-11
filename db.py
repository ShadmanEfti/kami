import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kami.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())
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


def add_message(conversation_id: int, role: str, content: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        conn.commit()
    finally:
        conn.close()


def get_messages(conversation_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
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


def get_latest_conversation_id():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM conversations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()