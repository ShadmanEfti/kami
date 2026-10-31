# KAMI — Knowledge-Aware Memory Interface

A chat interface that makes the model's context window visible and
controllable.

![KAMI demo: the user tells the model their name, the model repeats it, the user excludes those turns, the model no longer knows it, and /context shows exactly which messages were removed](docs/demo-context.gif)

## The problem

Every chatbot decides, invisibly, what reaches the model: which past
messages, which remembered facts, which system instructions. That
layer shapes every answer you get, and you can neither see it nor
change it. When the model recalls something you would rather it
forgot, or forgets something you told it, there is nothing to inspect.

KAMI treats context as the primary object. Every reply is stored with
the exact context that produced it, so you can **see** what the model
received, **explain** why its behaviour changed between two turns, and
**control** what reaches it next.

## What works today

- CLI chat against a local LLM via Ollama — no API keys, fully offline
- Conversations persisted in SQLite, resumable from a numbered menu
  with timestamps and previews
- **Per-reply context snapshots:** every reply is saved together with
  the system prompt, memories and history that produced it, plus the
  model, its options and the real token count Ollama reports
- **`/context [n]`** shows what the model saw for reply `[n]`, split
  into system prompt, memories and messages, and ends with what
  changed since the turn before
- **`/exclude n` / `/include n`** keep a turn out of the model's
  context, or put it back, without deleting anything
- Manual memory: store, list, and forget facts with slash commands
- **Automatic extraction, user-approved:** `/extract` asks the model to
  suggest memories from what you said; nothing is saved until you
  `/accept` it, and `/reject` stops the same suggestion coming back
- **Scoped memory:** a memory applies to every conversation by default,
  or only to the current one with `here`

## Milestone 2: Context Version Control

Forgetting a memory used to leave a gap. If a fact had already been
said in the conversation, it was still in the history the model
receives, and the model could repeat it. Phase 4 makes that layer
visible and editable.

Each reply now has a stored record of its context. `/context` shows it
in three segments, and compares it with the previous turn:

```
Context for [3] · qwen3.5:4b · 59 / 8,192 tokens · hash 8b2a484f

-- System prompt --
You are a helpful assistant.

-- Memories (2) --
 #8 Learning AI engineering through building projects.
 #9 mercedes and porsche i love most

-- Messages (1) --
 [3] You:       what is my name? reply in one line.

-- Changed since [2] --
 tokens    85 -> 59 (-26)
 messages  + [3] You: what is my name? reply in one line.
 messages  - [1] You: what is my name? reply in one line.
 messages  - [1] Assistant: Your name is Kabir.
 messages  - [2] You: what is my name? reply in one line.
```

What building and testing it showed:

- **Over-applied memory is visible.** With a stored memory about
  liking Porsche, the model worked cars into replies about coffee art
  and claimed _Red Dead Redemption 2_ has Porsche physics. The
  "Changed since" section showed the memory arriving at exactly the
  turn the behaviour started.
- **Forgetting is not enough.** With a memory forgotten but the
  history intact, the model once repeated the fact and once refused
  to. Excluding the turns removed it reliably.
- **Token counts are real, not estimated.** Ollama's
  `prompt_eval_count` was probed before use: an identical request
  repeated gave the same count, and a new turn grew it by the added
  content. One probe on one Ollama version, not a guarantee.

These come from hand-tested conversations, not a benchmark. Full
reasoning for every choice is in [docs/decisions.md](docs/decisions.md).

## Milestone 1: Memory System

![KAMI memory demo: the model suggests memories, the user accepts one and rejects one, a new conversation recalls the accepted fact, and after /forget a fresh conversation no longer knows it](docs/demo.gif)

The model suggests what to remember; the user decides. Extracted
memories land in a separate `memory_candidates` table and only reach
the prompt after explicit approval — the silent, self-deciding
behaviour KAMI exists to expose is turned into something you review.

What testing found with `llama3.2:3b`:

- Every fact stated in the test conversations was suggested.
- Every rejected suggestion was a model error: copying an existing
  memory into a "new" suggestion, or inventing a fact.
- The model copied existing memories **even with an explicit prompt
  rule against it.** A rule in the prompt is not a control; approval
  caught every case.

KAMI has since moved to `qwen3.5:4b`, which copied far less in first
tests.

## Quickstart

Requires Python 3.9+ and [Ollama](https://ollama.com).

```bash
ollama pull qwen3.5:4b
git clone https://github.com/ShadmanEfti/kami.git
cd kami
pip install -r requirements.txt
python3 chat.py
```

The database is created on first run, and upgraded in place when the
schema changes. To use another Ollama model, set `KAMI_MODEL`.

## Commands

| Command                   | Description                                           |
| ------------------------- | ----------------------------------------------------- |
| `/context [n]`            | Show what the model saw for reply n (default: latest) |
| `/exclude <n>`            | Keep turn n out of the model's context                |
| `/include <n>`            | Put turn n back into context                          |
| `/remember [here] <text>` | Store a memory (`here` = this conversation only)      |
| `/memories`               | List memories visible here, with source and scope     |
| `/forget <id>`            | Forget a memory                                       |
| `/extract`                | Suggest memories from this conversation               |
| `/pending`                | List suggestions waiting for a decision               |
| `/accept <id> [here]`     | Save a suggestion (`here` = this conversation only)   |
| `/reject <id>`            | Discard a suggestion and block it from returning      |
| `/help`                   | Show available commands                               |

Anything not starting with `/` is sent to the model. Replies are
numbered `[1]`, `[2]`, … per conversation; memories use `#id`.

## Known limitations

- Every active memory is injected on every turn, so a small model may
  work an unrelated memory into its replies. `/context` makes this
  visible; choosing which memories reach the model is later work.
- Exclusion is per turn: a question and its reply go together.
- Duplicates and rejected suggestions are matched exactly, so a
  reworded repeat can get through.
- Starting KAMI and exiting without chatting leaves an empty
  conversation in the menu.
- Replies from before snapshots existed have no recorded context.

## Design notes

Decisions and their reasoning are logged in
[docs/decisions.md](docs/decisions.md).

The recurring distinction throughout the codebase is between what the
user sees and what the model sees — `list_memories()` vs
`get_active_memories()`, the context segments vs the rendered payload,
a suggestion vs an accepted memory. Keeping those separate is the
point of the project.

A few rules the context layer keeps:

- **One place builds context.** `build_context()` is the only function
  that decides what reaches the model; exclusions are applied there
  and nowhere else.
- **A record, not a rebuild.** `/context` reads what was stored at the
  time, so forgetting or excluding something later never rewrites what
  an old reply actually saw.
- **A turn is saved whole or not at all.** The user message, the reply
  and its snapshot are written in one transaction, and only after a
  non-empty reply.
- **Numbers never shift.** Turn numbers are derived from the full
  history, so excluding a turn does not renumber the others.

## Roadmap

- [x] **Phase 1 — Foundation** · chat loop against a local model
- [x] **Phase 2 — Conversation System** · persistence and resume
- [x] **Phase 3 — Memory System** · manual memory, user-approved
      extraction, and scope (Milestone 1, `v0.1.0`)
- [x] **Phase 4 — Context Version Control** · per-reply snapshots,
      inspection, changes between turns, and turn exclusion
      (Milestone 2, `v0.2.0`)
- [ ] **Phase 5 — Visual Interface**
- [ ] **Phase 6 — RAG**
- [ ] **Phase 7 — Tools / Agents**
- [ ] **Phase 8 — Evaluation**
- [ ] **Phase 9 — Productionization**

## Stack

Python · SQLite · Ollama (qwen3.5:4b) · no external services
