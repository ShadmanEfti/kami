import db
from memory import get_active_memories

SYSTEM_INSTRUCTION="You are a helpful assistant."

def build_context(conversation_id,pending_user_message=None):
    memories=[{"id":m["id"],"content":m["content"]}
              for m in get_active_memories(conversation_id)]
    messages=db.get_messages(conversation_id)
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

def format_snapshot(snap,turn):
    lines=[f"Context for [{turn}] · {snap['model']} · hash {snap['payload_hash'][:8]}",""]

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
    k=0
    for m in snap["messages"]:
        if m["role"]=="user":
            k+=1
            lines.append(f" [{k}] You:       {_one_line(m['content'])}")
        else:
            lines.append(f"     Assistant: {_one_line(m['content'])}")

    return "\n".join(lines)+"\n"