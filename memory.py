from db import get_connection

def add_memory(content,conversation_id=None,source="manual"):

    content=content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty")

    conn=get_connection()
    try:
        cursor=conn.execute(
            """
            INSERT INTO memories (conversation_id,content,source)
            VALUES (?,?,?)
            """,
            (conversation_id,content,source),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def list_memories(conversation_id=None,include_inactive=False):

    clauses=[]
    params=[]

    if not include_inactive:
        clauses.append("is_active=1")

    if conversation_id is None:
        clauses.append("conversation_id IS NULL")

    else:
        clauses.append("conversation_id IS NULL OR conversation_id=?")
        params.append(conversation_id)

    sql="SELECT * FROM memories WHERE " + " AND ".join(clauses) + " ORDER BY id"

    conn=get_connection()
    try:
        rows=conn.execute(sql,params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def deactivate_memory(memory_id):

    conn=get_connection()
    try:
        cursor=conn.execute(
            "UPDATE memories SET is_active=0 WHERE id=? AND is_active=1",
            (memory_id,),
        )
        conn.commit()
        return cursor.rowcount>0
    finally:
        conn.close()

def get_active_memories(conversation_id=None):

    conn=get_connection()
    try:
        rows=conn.execute(
            """
            SELECT id,content FROM memories
            WHERE is_active=1 AND (conversation_id IS NULL OR conversation_id=?)
            ORDER BY id
            """,
            (conversation_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

