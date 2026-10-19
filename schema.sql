CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    source TEXT NOT NULL DEFAULT 'manual',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memory_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    content TEXT NOT NULL CHECK (length(trim(content))>0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
    memory_id INTEGER REFERENCES memories(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT,
    CHECK ((status='accepted')=(memory_id IS NOT NULL)),
    CHECK ((status='pending')=(decided_at IS NULL))
);

CREATE TABLE IF NOT EXISTS context_snapshots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    reply_message_id INTEGER UNIQUE REFERENCES messages(id),
    kind TEXT NOT NULL DEFAULT 'chat' CHECK (kind IN ('chat','extract')),
    system_prompt TEXT,
    memories TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(memories)),
    messages TEXT NOT NULL CHECK(json_valid(messages)),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    payload_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    options TEXT NOT NULL CHECK(json_valid(options)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((kind='chat')=(reply_message_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_conversation_id
    ON context_snapshots(conversation_id);
