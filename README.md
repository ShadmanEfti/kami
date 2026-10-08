# KAMI — Knowledge-Aware Memory Interface

A chat interface that makes the model's context window visible and
controllable.

![KAMI demo: the model suggests memories, the user accepts one and rejects one, a new conversation recalls the accepted fact, and after /forget a fresh conversation no longer knows it](docs/demo.gif)

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
- **Automatic extraction, user-approved:** `/extract` asks the model to
  suggest memories from what you said; nothing is saved until you
  `/accept` it, and `/reject` stops the same suggestion coming back
- **Scoped memory:** a memory applies to every conversation by default,
  or only to the current one with `here`
- `/memories` shows where each memory came from (typed or extracted)
  and where it applies — exactly what the model receives
- Memories injected into the system prompt on every turn, so forgetting
  takes effect immediately without a restart

Verified: injected facts recalled in a conversation with no history;
a forgotten fact dropped mid-conversation while other memories
survived; conversation-scoped memories and suggestions invisible from
other conversations; `/extract` failing cleanly with Ollama
unreachable; no slash command ever written to the conversation
history.

## Milestone 1: Memory System

The model suggests what to remember; the user decides. Extracted
memories land in a separate `memory_candidates` table and only reach
the prompt after explicit approval — the same silent, self-deciding
behaviour KAMI exists to expose is turned into something you review.

What testing found with `llama3.2:3b`:

- Every fact stated in the test conversations was suggested.
- Every rejected suggestion was a model error: copying an existing
  memory into a "new" suggestion, or inventing a fact.
- The model copied existing memories **even with an explicit prompt
  rule against it.** A rule in the prompt is not a control; approval
  caught every case.

These come from a small set of hand-tested conversations, not a
benchmark. Measuring extraction properly is Phase 8's job. Full
reasoning is in [docs/decisions.md](docs/decisions.md).

## Quickstart

Requires Python 3.9+ and [Ollama](https://ollama.com).

```bash
ollama pull llama3.2:3b
git clone https://github.com/ShadmanEfti/kami.git
cd kami
pip install -r requirements.txt
python3 chat.py
```

The database is created on first run.

## Commands

| Command                   | Description                                         |
| ------------------------- | --------------------------------------------------- |
| `/remember [here] <text>` | Store a memory (`here` = this conversation only)    |
| `/memories`               | List memories visible here, with source and scope   |
| `/forget <id>`            | Forget a memory                                     |
| `/extract`                | Suggest memories from this conversation             |
| `/pending`                | List suggestions waiting for a decision             |
| `/accept <id> [here]`     | Save a suggestion (`here` = this conversation only) |
| `/reject <id>`            | Discard a suggestion and block it from returning    |
| `/help`                   | Show available commands                             |

Anything not starting with `/` is sent to the model.

## Known limitations

- The 3B model sometimes copies existing memories or invents facts
  in its suggestions; review catches them, but they cost a `/reject`.
- Duplicates and rejected suggestions are matched exactly, so a
  reworded repeat can get through.
- `/forget` controls memory, but not conversation history: a fact
  stated earlier in the same conversation is still in the model's
  context. Controlling which history reaches the model is Phase 4.

## Design notes

Decisions and their reasoning are logged in
[docs/decisions.md](docs/decisions.md).

The recurring distinction throughout the codebase is between what the
user sees and what the model sees — `list_memories()` vs
`get_active_memories()`, the `messages` list vs the request payload,
a suggestion vs an accepted memory. Keeping those separate is the
point of the project.

## Roadmap

- [x] **Phase 1 — Foundation** · chat loop against a local model
- [x] **Phase 2 — Conversation System** · persistence and resume
- [x] **Phase 3 — Memory System** · manual memory, user-approved
      extraction, and scope (Milestone 1, `v0.1.0`)
- [ ] **Phase 4 — Context Version Control** · inspect and diff what
      reaches the model
- [ ] **Phase 5 — Visual Interface**
- [ ] **Phase 6 — RAG**
- [ ] **Phase 7 — Tools / Agents**
- [ ] **Phase 8 — Evaluation**
- [ ] **Phase 9 — Productionization**

## Stack

Python · SQLite · Ollama (llama3.2:3b) · no external services
