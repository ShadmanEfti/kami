import db
from config import MODEL,THINK,OLLAMA_OPTIONS
from context import build_context,render,diff_snapshots
from errors import NotFound,InvalidRequest,ModelUnavailable,EmptyReply
from extractor import extract_candidates,ExtractionError
from llm import call_model
from memory import get_active_memories,list_pending,list_rejected,add_candidate


def send_message(conversation_id,text):
    if not text or not text.strip():
        raise InvalidRequest("Message is empty.")

    ctx=build_context(conversation_id,text)
    payload=render(ctx)
    data=call_model(payload)

    reply=data.get("message",{}).get("content","")
    if not reply.strip():
        raise EmptyReply("Got an empty reply from the model. Nothing was save; try again.")

    prompt_tokens=data.get("prompt_eval_count")
    reply_tokens=data.get("eval_count")

    db.add_turn(conversation_id,text,reply,snapshot={
        "system_prompt":ctx["system"] if ctx["memories"] else None,
        "memories":ctx["memories"],
        "messages":ctx["messages"],
        "payload":payload,
        "model":MODEL,
        "prompt_tokens":prompt_tokens,
        "reply_tokens":reply_tokens,
        "options":{"think":THINK,**OLLAMA_OPTIONS},
    })

    return {
        "turn":db.count_turns(conversation_id),
        "reply":reply,
        "prompt_tokens":prompt_tokens,
        "reply_tokens":reply_tokens,
    }

def _reply_id(conversation_id,turn):
    reply_id=db.get_reply_id(conversation_id,turn)
    if reply_id is None:
        raise NotFound(f"No turn [{turn}] is in this conversation.")
    return reply_id

def get_turn_context(conversation_id,turn=None):
    if turn is None:
        turn=db.count_turns(conversation_id)
        if turn==0:
            raise NotFound("No reply yet in this conversation.")

    snapshot=db.get_snapshot(_reply_id(conversation_id,turn))
    if snapshot is None:
        raise NotFound(f"No context recorded for [{turn}] (before snapshot existed).")

    previous=None
    if turn>1:
        previous=db.get_snapshot(_reply_id(conversation_id,turn-1))

    return {
        "turn":turn,
        "snapshot":snapshot,
        "previous":previous,
        "diff":diff_snapshots(previous,snapshot) if previous else None,
    }

def extract_memories(conversation_id):
    history=build_context(conversation_id)["messages"]
    user_messages=[m["content"] for m in history if m["role"]=="user"]
    if not user_messages:
        raise InvalidRequest("Nothing to extract yet. Say something first.")

    existing=[m["content"] for m in get_active_memories(conversation_id)]
    existing+=[c["content"] for c in list_pending(conversation_id)]

    try:
        found=extract_candidates(user_messages,existing,list_rejected())
    except ExtractionError as e:
        raise ModelUnavailable(f"Extraction failed: {e}") from e

    return [{"id":add_candidate(text,conversation_id),"content":text} for text in found]

def set_exclusion(conversation_id,turn,excluded):
    reply_id=_reply_id(conversation_id,turn)
    return db.exclude_turn(reply_id) if excluded else db.include_turn(reply_id)

