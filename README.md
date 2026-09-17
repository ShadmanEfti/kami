# KAMI — Knowledge-Aware Memory Interface

A chat interface that makes the model's context window visible and
controllable.

## The problem

Every chatbot decides, invisibly, what reaches the model: which past
messages, which remembered facts, which system instructions. That
layer shapes every answer you get, and you can neither see it nor
change it. When the model recalls something you would rather it
forgot, or forgets something you told it, there is nothing to inspect.

KAMI treats context as the primary object. Memories are stored
explicitly, listed on demand, revocable at any time, and rebuilt into
the prompt on every single turn — so what the model knows is always
something you can look at and edit.

## What works today

- CLI chat against a local LLM via Ollama — no API keys, fully offline
- Conversations persisted in SQLite, resumable from a numbered menu
  with timestamps and previews
- Manual memory: store, list, and forget facts with slash commands
- Memories injected into the system prompt on every turn, so forgetting
  takes effect immediately without a restart
- Memories persist across conversations — a brand new conversation
  starts already knowing what you have told KAMI

Verified: injected facts recalled in a conversation with no history;
a forgotten fact dropped mid-conversation while other memories
survived; UTF-8 and quoted content round-tripping intact.

## Quickstart

Requires Python 3.9+ and [Ollama](https://ollama.com).

```bash
ollama pull llama3.2:3b
git clone https://github.com/ShadmanEfti/kami.git
cd kami
pip install requests
python3 chat.py
```

The database is created on first run.

## Commands

| Command            | Description             |
| ------------------ | ----------------------- |
| `/remember <text>` | Store a memory          |
| `/memories`        | List stored memories    |
| `/forget <id>`     | Forget a memory         |
| `/help`            | Show available commands |

Anything not starting with `/` is sent to the model.

## Design notes

Decisions and their reasoning are logged in
[docs/decisions.md](docs/decisions.md).

The recurring distinction throughout the codebase is between what the
user sees and what the model sees — `list_memories()` vs
`get_active_memories()`, the `messages` list vs the request payload.
Keeping those separate is the point of the project.

## Roadmap

- [x] **Phase 1 — Foundation** · chat loop against a local model
- [x] **Phase 2 — Conversation System** · persistence and resume
- [ ] **Phase 3 — Memory System** · manual store and injection done;
      automatic extraction next
- [ ] **Phase 4 — Context Version Control** · inspect and diff what
      reaches the model
- [ ] **Phase 5 — Visual Interface**
- [ ] **Phase 6 — RAG**
- [ ] **Phase 7 — Tools / Agents**
- [ ] **Phase 8 — Evaluation**
- [ ] **Phase 9 — Productionization**

## Stack

Python · SQLite · Ollama (llama3.2:3b) · no external services
