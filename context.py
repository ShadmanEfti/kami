import db
from memory import get_active_memories

def build_system_prompt(memories):
    if not memories:
        return None
    lines="\n".join(f"- {m['content']}" for m in memories)
    return f"You are a helpful assistant.\n\nKnown facts about the user:\n{lines}"

def build_context(conversation_id,pending_user_message=None):
    memories=get_active_memories(conversation_id)
    system_prompt=build_system_prompt(memories)
    history=db.get_messages(conversation_id)

    if pending_user_message is not None:
        history=history+[{"role":"user","content":pending_user_message}]

    if system_prompt is None:
        return history
    return [{"role":"system","content":system_prompt}]+history

