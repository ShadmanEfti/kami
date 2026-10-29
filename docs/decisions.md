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

Resolved 2026-10-25: see the migration entry.

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

## 2026-09-22 — Extracted memories are proposed, never saved

Automatic extraction produces candidates, not memories. Nothing
reaches the `memories` table until the user accepts it with
`/accept`. A rejected candidate never enters the model's context.

An extractor that writes straight to memory is the silent,
self-deciding behaviour KAMI exists to expose. The model decides what
might be worth remembering; the user decides what is remembered. A 3B
model will propose trivial or invented facts, and approval turns those
misfires from silent prompt pollution into something the user sees and
declines.

Cost accepted: every memory now costs the user a decision. That
friction is the point at this stage.

Revisit when: measured extractor precision is high enough to justify
auto-saving low-risk categories — a question for the evaluation
harness, not intuition.

## 2026-09-22 — Extraction runs on demand, not after every reply

`/extract` runs the extractor over the current conversation when the
user asks. Nothing runs automatically after a turn.

Each extraction is a second full model call. On the development
machine (8GB M1, `llama3.2:3b`), running it every turn would add a
second wait to every reply, for a pass that finds nothing in most
messages. On-demand also keeps the user in control of _when_ memory is
built, not only _what_ goes into it.

Like the other slash commands, `/extract` is control-plane: the
extraction prompt and its output never enter `messages` or the
`messages` table.

Revisit when: extraction is cheap enough to run in the background.
The extractor is a plain function with no trigger logic inside it, so
an automatic trigger is a later call to the same function, not a
redesign.

## 2026-09-25 — Candidates live in their own table

Proposals go into `memory_candidates`; `memories` only ever holds what
the user accepted.

Rejected alternative: a `status` column on `memories`. Every read path
(`get_active_memories()`, `list_memories()`) would then have to
remember to filter out unapproved rows, and one missed `WHERE` clause
would leak unapproved text into the prompt. A separate table makes
that leak structurally impossible. It also needed no migration:
adding a table is a `CREATE TABLE IF NOT EXISTS`, while altering
`memories` would have forced another rebuild.

Rejected candidates are kept, not deleted. Accepted ÷ proposed is the
extractor's precision — the first real metric for the evaluation
harness.

Integrity lives in the schema, not only in the code: `status` is
limited to `pending`/`accepted`/`rejected`, an accepted candidate must
point at a memory (`(status='accepted') = (memory_id IS NOT NULL)`),
and only decided candidates carry a decision time
(`(status='pending') = (decided_at IS NULL)`). `accept_candidate()`
inserts the memory and updates the candidate on one connection with
one commit, so neither can happen without the other.

Verified: a blank content, an unknown status, an `accepted` row with
no memory and a nonexistent conversation id were each rejected by the
matching constraint.

## 2026-09-25 — Memory scope is chosen at accept time

`/accept <id>` saves a memory globally; `/accept <id> here` saves it
to the current conversation only. `/remember [here] <text>` scopes
manual memories the same way.

In `memories`, `conversation_id` means scope, not provenance: NULL is
injected into every conversation, an id only into that one. Where an
extracted memory came from is recorded in `memory_candidates`, which
points at the memory it became.

Global is the default because most extracted facts are about the user
(name, projects, preferences) and hold everywhere; scoping to one
conversation is the exception you opt into.

Candidates follow the same visibility rule as memories: `/pending`,
`/accept` and `/reject` only see candidates tied to no conversation
plus the current conversation's. Without it, accepting a candidate by
id from another conversation would make `here` mean the conversation
it was extracted in rather than the one the user is in.

`here` leads for `/remember` (free text follows) and trails for
`/accept` (an id comes first), so neither can be confused with memory
content.

## 2026-10-07 — Extraction prompt kept after the fixture run

The extraction prompt passed all three fixtures unchanged: the
fact-rich case returned one memory per stated fact, and the no-facts
and transient cases both returned an empty list. Duplicate filtering
against existing memories worked, and an unreachable Ollama raised
`ExtractionError` rather than returning an empty result.

The fixtures are easy cases and all ran with no existing memories,
which later proved to hide most of the real failures (see the next
entry). Deferred to the evaluation harness: several facts in one
sentence, a fact mixed with a mood, facts about other people, changes
of mind, hypotheticals, and every case run again with existing
memories present.

## 2026-10-07 — Copied memories are caught by review, not by the prompt

With memories present, `llama3.2:3b` repeatedly copied entries from
the `Existing memories` section into its suggestions, sometimes word
for word, sometimes reworded or translated. It did so with an explicit
rule against it in the prompt; the rule was confirmed present in the
file the chat loaded.

Two other failure modes appeared in testing: inventing comparisons
between a stated fact and an existing memory ("User prefers X over AI
engineering"), and missing one of two facts stated in a single
sentence.

Rejected for now: a grounding check that drops suggestions whose
content words do not appear in the user's messages. It targets the
observed failure, but every leak is already caught by approval, and a
stronger model plus embedding-based comparison (RAG milestone) may
make it unnecessary.

The lesson stands regardless of the fix: a rule in the prompt is not a
control. A 3B model will ignore it, so anything that must hold is
enforced in code or by the user.

Revisit when: switching to a stronger model, or when the RAG layer
provides embeddings.

## 2026-10-07 — Duplicate detection has two layers

Suggestions are checked twice. The model is told to skip anything
already listed, which catches reworded repeats when it complies.
`normalize()` then drops anything matching an existing memory, a
pending suggestion or a rejected suggestion after case-folding,
trimming and removing a trailing period, which catches exact repeats
reliably.

Rejected suggestions block repeats in every conversation, not only the
one they were rejected in: a rejection is a judgement about the fact,
and that judgement does not change between conversations. They are
passed to the extractor separately and never shown to the model, since
listing them as existing memories would present rejected facts as
true.

Known gap, seen in testing: a rejected suggestion can return in
different words, which exact matching cannot catch. Closing it needs
semantic comparison.

## 2026-10-07 — "Found nothing" and "failed" are different results

`extract_candidates()` returns an empty list when the model ran and
found nothing worth keeping, and raises `ExtractionError` when the
request, the response or the JSON failed. Collapsing the two would
make `/extract` report "no suggestions" while Ollama was down.

Connection failures and timeouts get short messages for the chat; the
underlying exception is kept on `__cause__` for debugging.

## 2026-10-08 — Accept/reject rate is not extraction precision

`memory_candidates` records whether each suggestion was accepted, not
why one was rejected. A suggestion rejected because the model copied
or invented it, and one rejected because the user did not want a
correct fact stored, look the same.

Reported figures for Milestone 1 therefore come from reviewing each
suggestion by hand: in the first test run, all three stated facts were
captured, and all four rejections were model errors (three copied
memories, one invented). This is a handful of hand-tested
suggestions, not a benchmark.

Deferred to the evaluation harness: record a reason on rejection
(`copied`, `invented`, `not wanted`), so precision can be computed
from the table.

## 2026-10-08 — Demo recorded from a fresh database

The Milestone 1 demo was recorded after moving the test database out
of the repository and starting empty. Old test memories were changing
the model's replies (a stray memory about Japanese made it greet the
user in Japanese), and an empty start can be recreated exactly, which,
with extraction at temperature 0, made rehearsal and recording produce
the same suggestions.

The previous database is kept outside the repository as the record of
the testing behind the figures above.

## 2026-10-11 — Default model switched to qwen3.5:4b

`llama3.2:3b` kept copying existing memories into its suggestions (see
2026-10-07), so the default is now `qwen3.5:4b`. On the first
extraction test it returned only stated facts, and picked up a
correction the user made mid-conversation. One run, not a benchmark.

Qwen3.5 has thinking on by default in Ollama. A "say hi" prompt
produced over 4,000 reasoning tokens in four minutes and never
answered. Every request now sends `"think": false` explicitly.

The model is read from `KAMI_MODEL`, defaulting to `qwen3.5:4b`, so
switching models is a config change, not a code change.

Deferred: comparing `llama3.2:3b`, `qwen3.5:4b` and the OpenAI API
until after Phases 4 and 5, so the comparison covers the whole system.

## 2026-10-11 — Context window set to 8192

Ollama defaults to a 4096-token window, and anything past it is
dropped silently. Since memories and history share that window, a
full context would look like a memory bug.

Cost on the 8GB M1: the model grows from 3.1 GB fully on GPU to
3.9 GB split 18/82 CPU/GPU, and generation drops from about 17.7 to
about 16 tok/s. Slightly slower replies are acceptable; losing context
without warning is not.

Chat and extraction share the same `OLLAMA_OPTIONS` from `config.py`.
Ollama reloads the model when `num_ctx` differs between requests,
which would add a ~5s load every time the user switched between
chatting and `/extract`.

## 2026-10-11 — `/forget` does not reach conversation history

Forgetting a memory removes it from the system prompt, but if the fact
was already said in the conversation, the history still carries it to
the model. Tested: after `/forget`, the model still answered with the
forgotten name, taken from its own earlier reply.

Not fixed here. Controlling what history reaches the model is Phase 4's
job, and this is the clearest case for it.

## 2026-10-14 — One function builds what reaches the model

`build_context()` in `context.py` is now the only place a chat payload
is assembled: active memories become the system prompt, and the
conversation's saved messages follow it. `chat.py` sends its result
unchanged.

History is read from SQLite on every call rather than kept in an
in-memory list that mirrors the table. There is one copy of the
conversation, so what the model sees cannot drift from what is stored.
The message being answered is not saved yet (see the next entry), so
it is passed in explicitly as `pending_user_message`.

The function has no side effects: no printing, no writes. Phase 4
needs a single point where context exists as a value, so it can be
snapshotted, shown and diffed. A payload assembled in pieces across
the chat loop cannot be.

Verified: a resumed conversation still recalled its history, and
`/remember` and `/forget` both took effect on the next turn.

## 2026-10-14 — A turn is saved whole or not at all

The user's message is no longer saved before the request. After a
non-empty reply, `add_turn()` inserts the user message and the reply
on one connection with one commit, and returns the reply's id.

Before, the user message was written first. When Ollama returned an
empty reply, the guard skipped saving the assistant turn but the user
message stayed, so the next request sent two user messages in a row.
A timeout or HTTP error left the same orphan behind. Now an empty
reply, a timeout or a crash saves nothing.

Two separate `add_message()` calls were rejected: a failure between
them leaves the same half-turn, only more rarely.

The returned id gives each reply a stable handle, which context
snapshots can point at.

Verified: after a normal turn, the latest four rows in `messages`
alternate user/assistant (ids 53–56).

## 2026-10-20 — One segmented snapshot per reply

Every reply gets a row in `context_snapshots` recording what produced
it: the system instruction, the injected memories (with ids), the
history (with ids), the exact payload, the model and the options,
including `think`. It is saved inside `add_turn()`'s transaction, so a
reply never exists without the context behind it.

Segments rather than only the payload, because inspection needs to
show system prompt, memories and history separately, and the payload
merges memories into one string with no ids. The payload is stored as
well, so the record stays exact if the prompt template changes.

The payload is serialised canonically (sorted keys, fixed separators)
before hashing, so identical context gives an identical hash. That is
what `/diff` will use to report "unchanged". `json_valid` checks keep a
malformed segment out of the table.

A system message is still sent only when memories exist, preserving
pre-Phase-4 behaviour; `system_prompt` is NULL when none was sent.

Verified: two fresh conversations sending "hi" with the same memory
produced the same hash (`3a944ec1`); a second turn's snapshot held 3
messages to the first's 1; the pending user message's id was filled in
(59 for reply 60); `/extract` added no snapshot.

## 2026-10-21 — Replies are numbered per conversation, by derivation

Replies print as `Assistant [n]`, where n counts from 1 within the
conversation. Global message ids (`#60`, `#62`) were shown before:
they jumped by two, climbed across conversations, and meant nothing
to the user.

The turn number is derived, not stored. `count_turns()` counts the
conversation's assistant messages; `get_reply_id()` resolves turn n
to the n-th one by id. `messages.id` stays the real key, and snapshots
still point at it. No new column means nothing to keep in sync, and
when retry and edit arrive, deciding which version "turn 3" means
changes one query rather than stored data.

Numbers are scoped to the current conversation, matching how
candidates already work. Square brackets keep turns visually distinct
from memory ids, which use `#`.

The printed number is re-counted from the database after each turn
instead of tracked in a variable, so resuming needs no special case.

Verified: a new conversation printed [1] then [2]; resuming it printed
[3]; turn 0 and a turn past the end both resolved to None.

## 2026-10-24 — `/context` shows the record, not a rebuild

`/context [n]` resolves turn n to its reply and prints that reply's
snapshot in three segments: system prompt, memories, messages. With no
number it shows the latest turn.

It reads the stored snapshot rather than calling `build_context()`
again. Rebuilding would show today's memories and exclusions, not what
the model actually saw: a memory forgotten since would vanish from an
old turn's context, which is exactly the kind of silent rewrite KAMI
exists to prevent.

The history ends on the user message being answered; a reply is never
part of its own context. Turn numbers inside it are derived from the
alternating order `add_turn()` guarantees.

Long text is cut to one line, since the CLI is for scanning. Formatting
is a separate function from loading, so the GUI panel can read the same
snapshot dict and ignore the terminal layout.

Replies from before snapshots existed report that no context was
recorded rather than reconstructing one.

Verified: in one conversation, a memory added between turns was absent
from [1]'s context and present in [2]'s, with different hashes;
repeated `/context` calls returned the same hash; `/context` added no
rows to `messages`.

## 2026-10-25 — Snapshots record real token counts; first migration

Each snapshot stores `prompt_tokens` (Ollama's `prompt_eval_count`)
and `reply_tokens` (`eval_count`). `/context` shows the first against
the window the snapshot actually ran under, e.g. `124 / 8,192 tokens`,
read from the snapshot's own `options` rather than the current config.

Probed before building, since prompt-prefix reuse could have made the
count cover only newly processed tokens. An identical request repeated
returned the same count (34, 34), and adding a turn grew it by the
added content (130). It reports the full context size. One probe on
one Ollama version, not a guarantee.

Both columns are nullable. Snapshots from before this change say
"tokens not recorded" rather than showing an estimate.

First real migration. `CREATE TABLE IF NOT EXISTS` never alters an
existing table, so `_migrate()` runs at every startup and adds any
missing column after checking `PRAGMA table_info`. It is a no-op on a
fresh database, where `schema.sql` already defines the columns, and on
every later run. Consequence: column order differs between migrated
and fresh databases, so code must never rely on column position. All
inserts name their columns and all reads go through `dict(row)`.

Verified: migration added both columns to the existing database and
repeated runs raised nothing; a fresh database got them from
`schema.sql`; counts grew from 65 to 124 across two turns; an older
snapshot reported no count.

## 2026-10-29 — Changes are shown inside `/context`, not as `/diff`

Each `/context n` ends with "Changed since [n−1]": tokens before and
after, memories added or removed, messages added or removed, and any
change to the system prompt, model or options.

Planned as a separate `/diff a b`, then folded into `/context`. The
question that matters is "why did the model behave differently at this
turn?", which always compares with the turn before, and the GUI panel
will show it in the same place as the context. Arbitrary pairs can
come later if missed.

The payload hash cannot answer it: consecutive turns always differ,
because each history contains the last plus two new messages. So the
diff separates normal growth (the previous reply and the new question,
appended at the end) from everything else. Normal growth is collapsed
to one line; anything else is listed.

Messages and memories are matched by id, not content, so a repeated
"hi" is not mistaken for the same message. `diff_snapshots()` returns
plain data with ids for the GUI; `format_changes()` turns message ids
into turn labels for the terminal.

Verified: a memory added between turns showed as `+ #7`; a memory
forgotten showed as `- #5` together with the system prompt dropping,
which explained why a full exchange added only 14 tokens; the first
turn reports nothing to compare.
