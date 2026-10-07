from db import get_connection

# In memories and memory_candidates, conversation_id is SCOPE:
#   NULL    -> global, visible from every conversation
#   an id   -> visible only inside that conversation

VALID_SCOPES=("global","conversation")

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
        clauses.append("(conversation_id IS NULL OR conversation_id=?)")
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

def add_candidate(content,conversation_id=None):

    content=content.strip()
    if not content:
        raise ValueError("Candidate content cannot be empty")

    conn=get_connection()
    try:
        cursor=conn.execute(
            """
            INSERT INTO memory_candidates (conversation_id,content)
            VALUES (?,?)
            """,
            (conversation_id,content),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def list_pending(conversation_id=None):

    conn=get_connection()
    try:
        rows=conn.execute(
            """
            SELECT * FROM memory_candidates
            WHERE status='pending'
            AND (conversation_id IS NULL OR conversation_id=?)
            ORDER BY id 
            """,
            (conversation_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def accept_candidate(candidate_id,conversation_id=None,scope="global"):

    if scope not in VALID_SCOPES:
        raise ValueError(f"Unknown scope {scope!r}; expected 'global' or 'conversation'")

    if scope=="conversation" and conversation_id is None:
        raise ValueError("Not in a conversation, so there is nothing to scope to")

    memory_conversation_id=conversation_id if scope=="conversation" else None

    conn=get_connection()
    try:
        row=conn.execute(
            """
            SELECT content FROM memory_candidates
            WHERE id=? AND status='pending'
            AND (conversation_id IS NULL OR conversation_id=?)
            """,
            (candidate_id,conversation_id),
        ).fetchone()
        if row is None:
            return False

        cursor=conn.execute(
            """
            INSERT INTO memories (conversation_id,content,source)
            VALUES (?,?,'extracted')
            """,
            (memory_conversation_id,row["content"]),
        )
        memory_id=cursor.lastrowid

        cursor=conn.execute(
            """
            UPDATE memory_candidates
            SET status='accepted',memory_id=?,decided_at=datetime('now')
            WHERE id=? AND status='pending'
            """,
            (memory_id,candidate_id),
        )
        if cursor.rowcount==0:
            conn.rollback()
            return False
        conn.commit()
        return True

    except Exception :
        conn.rollback()
        raise
    
    finally:
        conn.close()

def reject_candidate(candidate_id,conversation_id=None):

    conn=get_connection()
    try:
        cursor=conn.execute(
            """
            UPDATE memory_candidates
            SET status='rejected',decided_at=datetime('now')
            WHERE id=? AND status='pending'
            AND (conversation_id IS NULL OR conversation_id=?)
            """,
            (candidate_id,conversation_id),
        )
        conn.commit()
        return cursor.rowcount>0
    finally:
        conn.close()

def list_rejected():

    conn=get_connection()
    try:
        rows=conn.execute(
            """
            SELECT content FROM memory_candidates
            WHERE status='rejected'
            """
        ).fetchall()
        return [row["content"] for row in rows]
    finally:
        conn.close()
        
