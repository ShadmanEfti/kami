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