# Decisions

A running log of design decisions in KAMI: what was chosen, why, and
what was rejected. Newest last.

---

## 2026-09-09 — SQLite before Postgres

Chose SQLite for persistence rather than starting with Postgres.

Single-user local tool, no concurrent writers, and zero setup cost for
anyone cloning the repo. Postgres would add a service to run and
credentials to manage in exchange for capabilities the project does not
yet need. The schema is plain SQL, so migrating later is a contained
change rather than a rewrite.

Revisit when: multiple clients need concurrent write access.

## 2026-09-12 — Reverted the retry/backoff wrapper around Ollama calls

Built retry-with-backoff for the Ollama request, then removed it in
favour of a simple empty-reply guard.

The failure it defended against (Ollama cold-loading the model on the
first request) was slow, not flaky, and retrying made it worse by
issuing a second request against an already-loading model. The wrapper
added a layer of indirection that obscured real errors during
debugging. The guard that survived — skip the turn and warn if the
reply is empty — covers the failure that actually occurred.

Lesson kept: build for observed failures, not imagined ones.

## 2026-09-16 — Memory content validated at both the edge and the schema

`add_memory()` strips input and raises `ValueError` on empty content;
the `memories` table also has `CHECK (length(trim(content)) > 0)`.

Deliberately redundant. The Python check exists to produce a useful
message to the user; the schema check exists so that nothing else —
a future extraction pipeline, a stray `sqlite3` command, a bug —
can write a blank row. Validating at the edge for UX and at the
boundary for integrity are different jobs.

## 2026-09-16 — Soft delete instead of hard delete

Forgetting a memory sets `is_active = 0`. Rows are never deleted.

Forgetting stays inspectable, which is what Phase 4's context version
control will build on: you cannot show a user what changed in their
context if the removed state is gone. `deactivate_memory()` returns
whether a row actually changed, so "no such id" and "already forgotten"
are distinguishable from a real change.

Cost accepted: the table only grows. Not a concern at the scale of a
single user's memories.

## 2026-09-16 — Deferred a migration story

Adding the content CHECK constraint to an existing table is not
possible with SQLite's `ALTER TABLE`. Dropped and recreated `kami.db`
instead of writing a migration.

There is no data yet that cannot be regenerated. A migration path
becomes necessary the moment KAMI is used for real rather than tested,
which is the trigger to revisit this — likely at the end of Phase 3,
once the memory store holds anything worth keeping.

## 2026-09-16 — Slash commands are control-plane, not conversation

`/remember`, `/memories`, `/forget` and `/help` are intercepted before
the message history is touched. They are never written to the
`messages` table and never sent to the model.

The user issuing a command is talking _to_ KAMI, not _through_ it.
Mixing the two would mean a resumed conversation replays `/forget 3`
at the model as if it were dialogue.

Verified: 11 commands issued in one session, 0 rows added to
`messages`.

## 2026-09-16 — The system prompt is derived state, not stored state

Active memories are read and the system message is rebuilt on every
turn, rather than assembled once at startup or persisted alongside the
conversation.

Two consequences, both wanted. A `/forget` takes effect on the very
next message with no restart. And context is always reconstructable
from the memory table rather than frozen in a snapshot — which is the
precondition for Phase 4 being able to diff and version it.

Implementation note: the payload is built as a new list
(`[system] + messages`) rather than by inserting into `messages`,
which would accumulate a stale system message every turn.

## 2026-09-16 — Two read paths, two audiences

`list_memories()` returns full rows for the user to inspect.
`get_active_memories()` returns only `id` and `content` for injection
into the model's context.

The SQL overlaps today, but they answer different questions and will
diverge. Keeping the distinction visible in the function names is
deliberate: the gap between what the user sees and what the model sees
is the thing KAMI exists to expose.
