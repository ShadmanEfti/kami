import db
from memory import get_active_memories

SYSTEM_INSTRUCTION="You are a helpful assistant."

def build_context(conversation_id,pending_user_message=None):
    memories=[{"id":m["id"],"content":m["content"]}
              for m in get_active_memories(conversation_id)]
    
    excluded=db.get_excluded_reply_ids(conversation_id)
    messages=[]
    for m in db.get_messages(conversation_id):
        if m["role"]=="assistant" and m["id"] in excluded:
            while messages and messages[-1]["role"]=="user":
                messages.pop()
            continue
        messages.append(m)
        
    if pending_user_message is not None:
        messages=messages+[{"id":None,"role":"user","content":pending_user_message}]
    return {"system":SYSTEM_INSTRUCTION,"memories":memories,"messages":messages}

def render(ctx):
    history=[{"role":m["role"],"content":m["content"]} for m in ctx["messages"]]
    if not ctx["memories"]:
        return history
    facts="\n".join(f"- {m['content']}" for m in ctx["memories"])
    system=f"{ctx['system']}\n\nKnown facts about the user:\n{facts}"
    return [{"role":"system","content":system}]+history

def _one_line(text,width=80):
    text=" ".join(text.split())
    return text if len(text)<=width else text[:width-1]+"..."

def diff_snapshots(old,new):
    old_mem={m["id"]:m for m in old["memories"]}
    new_mem={m["id"]:m for m in new["memories"]}
    old_msg={m["id"]:m for m in old["messages"]}
    new_msg={m["id"]:m for m in new["messages"]}

    added=[m for i,m in new_msg.items() if i not in old_msg]
    tail=new["messages"][-2:]

    return {
        "memories_added":  [m for i,m in new_mem.items() if i not in old_mem],
        "memories_removed":[m for i,m in old_mem.items() if i not in new_mem],
        "messages_added":  added,
        "messages_removed":[m for i,m in old_msg.items() if i not in new_msg],
        "expected_growth": added==tail and [m["role"] for m in tail]==["assistant","user"],
        "system_changed":  old["system_prompt"]!=new["system_prompt"],
        "model":           (old["model"],new["model"]),
        "options_changed": old["options"]!=new["options"],
        "tokens":          (old.get("prompt_tokens"),new.get("prompt_tokens"))
    }

def turn_labels(conversation_id):
    labels,pending,k={},[],0
    for m in db.get_messages(conversation_id):
        if m["role"]=="user":
            pending.append(m["id"])
        else:
            k+=1
            labels[m["id"]]=f"[{k}] Assistant"
            for uid in pending:
                labels[uid]=f"[{k}] You"
            pending=[]
    for uid in pending:
        labels[uid]=f"[{k+1}] You"

    return labels

def format_snapshot(snap,turn,labels):
    tokens=snap.get("prompt_tokens")
    limit=snap["options"].get("num_ctx")
    if tokens is None:
        size="tokens not recorded"
    elif limit:
        size=f"{tokens:,} / {limit:,} tokens"
    else:
        size=f"{tokens:,} tokens"
    lines=[f"Context for [{turn}] · {snap['model']} · {size} · hash {snap['payload_hash'][:8]}",""]

    lines.append("-- System prompt --")
    lines.append(snap["system_prompt"] or "(none sent)")
    lines.append("")

    lines.append(f"-- Memories ({len(snap['memories'])}) --")
    if not snap["memories"]:
        lines.append("(none)")
    for m in snap["memories"]:
        lines.append(f" #{m['id']} {_one_line(m['content'])}")
    lines.append("")

    lines.append(f"-- Messages ({len(snap['messages'])}) --")
    for m in snap["messages"]:
        if m["role"]=="user":
            lines.append(f" {labels[m['id']]+':':<15}{_one_line(m['content'])}")
        else:
            lines.append(f" {labels[m['id']]+':':<15}{_one_line(m['content'])}")

    return "\n".join(lines)+"\n"

def format_changes(diff,labels,prev_turn):
    lines=[f"-- Changed since [{prev_turn}] --"]

    before,after=diff["tokens"]
    if before is not None and after is not None:
        lines.append(f" tokens    {before:,} -> {after:,} ({after-before:+,})")

    for m in diff["memories_added"]:
        lines.append(f" memory    + #{m['id']}  {_one_line(m['content'])}")
    for m in diff["memories_removed"]:
        lines.append(f" memory    - #{m['id']}  {_one_line(m['content'])}")

    if diff["expected_growth"]:
        lines.append(f" messages  +2 (normal growth: [{prev_turn}] reply, [{prev_turn+1}] You)")
    else:
        for m in diff["messages_added"]:
            lines.append(f" messages  + {labels[m['id']]}: {_one_line(m['content'])}")

    for m in diff["messages_removed"]:
        lines.append(f" messages  - {labels[m['id']]}: {_one_line(m['content'])}")

    if diff["system_changed"]:
        lines.append(" system prompt changed")
    if diff["model"][0]!=diff["model"][1]:
        lines.append(f" model    {diff['model'][0]} -> {diff['model'][1]}")
    if diff["options_changed"]:
        lines.append(" options changed")

    return "\n".join(lines)+"\n"
    