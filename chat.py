import requests
import db
from context import build_context,render,format_snapshot
from datetime import datetime,timezone
from memory import (
    add_memory,list_memories,deactivate_memory,get_active_memories,
    add_candidate,list_pending,accept_candidate,reject_candidate,list_rejected
)
from extractor import extract_candidates,ExtractionError
from config import OLLAMA_URL,MODEL,THINK,OLLAMA_OPTIONS

HELP_TEXT="""Commands:
  /remember [here] <text>  Store a memory (here = this conversation only)
  /memories                List memories visible here
  /forget <id>             Forget a memory
  /extract                 Suggest memories from this conversation
  /pending                 List suggestions waiting for a decision
  /accept <id> [here]      Save a suggestion (here = this conversation only)
  /reject <id>             Discard a suggestion
  /context [n]             Show what the model saw for reply n (default: latest)
  /help                    Show this message"""

def print_conversation_menu(conversations):

    for i, c in enumerate(conversations, start=1):
        ts = datetime.strptime(c["created_at"], "%Y-%m-%d %H:%M:%S")
        ts = ts.replace(tzinfo=timezone.utc).astimezone()
        when = ts.strftime("%b %-d, %-I:%M %p")
        count = c["message_count"]
        label = "message" if count == 1 else "messages"
        preview = c["preview"]
        if preview is None:
            preview = "(empty)"
        elif len(preview) > 40:
            preview = preview[:40] + "..."
        print(f"{i}. {when} — {count} {label} — \"{preview}\"")

def split_scope(text):

    parts=text.split(maxsplit=1)
    if len(parts)==2 and parts[0].lower()=="here":
        return "conversation",parts[1]
    return "global",text

def handle_command(user_input,conversation_id):

    parts=user_input.split(maxsplit=1)
    command=parts[0].lower()
    argument=parts[1] if len(parts)>1 else ""

    if command=="/remember":
        if argument.strip().lower()=="here":
            print("Usage: /remember [here] <text>\n")
        else:
            scope,content=split_scope(argument)
            target=conversation_id if scope=="conversation" else None
            try:
                memory_id=add_memory(content,conversation_id=target)
                label="this conversation only" if target else "global"
                print(f"Remembered #{memory_id} ({label})\n")
            except ValueError as e:
                print(f"Error: {e}\n")

    elif command=="/memories":
        memories=list_memories(conversation_id)
        if not memories:
            print("No memories stored yet.\n")
        else:
            for m in memories:
                where="global" if m["conversation_id"] is None else "this conversation"
                print(f" [{m['id']}] ({m['source']} · {where}) {m['content']}")
            print("")

    elif command=="/forget":
        if not argument.isdigit():
            print("Usage: /forget <id>\n")
        elif deactivate_memory(int((argument))):
           print(f"Forgot memory #{argument}\n")
        else:
            print(f"No active memory with id {argument}\n")

    elif command=="/extract":
        history=db.get_messages(conversation_id)
        user_messages=[m["content"] for m in history if m["role"]=="user"]
        if not user_messages:
            print("Nothing to extract yet. Say something first.\n")
            return

        existing=[m["content"] for m in get_active_memories(conversation_id)]
        existing+=[c["content"] for c in list_pending(conversation_id)]

        print("Extracting...",flush=True)
        try:
            found=extract_candidates(user_messages,existing,list_rejected())
        except ExtractionError as e:
            print(f"Extraction failed: {e}\n")
            return

        if not found:
            print("No new memories suggested.\n")
            return

        print("Suggested memories:")
        for text in found:
            candidate_id=add_candidate(text,conversation_id)
            print(f" [{candidate_id}] {text}")
        print("/accept <id> [here] · /reject <id>\n")

    elif command=="/pending":
        pending=list_pending(conversation_id)
        if not pending:
            print("No pending suggestions.\n")
        else:
            for c in pending:
                where="global" if c["conversation_id"] is None else "this conversation"
                print(f" [{c['id']}] ({where}) {c['content']}")
            print("/accept <id> [here] · /reject <id>\n")

    elif command=="/accept":
        words=argument.split()
        if len(words)==1 and words[0].isdigit():
            scope="global"
        elif len(words)==2 and words[0].isdigit() and words[1].lower()=="here":
            scope="conversation"
        else:
            print("Usage: /accept <id> [here]\n")
            return

        candidate_id=int(words[0])
        try:
            accepted=accept_candidate(candidate_id,conversation_id,scope)
        except ValueError as e:
            print(f"Error: {e}\n")
            return

        if accepted:
            label="this conversation only" if scope=="conversation" else "global"
            print(f"Accepted #{candidate_id} ({label})\n")
        else:
            print(f"No pending suggestion #{candidate_id} here\n")

    elif command=="/reject":
        if not argument.isdigit():
            print("Usage: /reject <id>\n")
        elif reject_candidate(int(argument),conversation_id):
            print(f"Rejected #{argument}\n")
        else:
            print(f"No pending suggestion #{argument} here\n")

    elif command=="/context":
        if argument=="":
            turn=db.count_turns(conversation_id)
            if turn==0:
                print("No reply yet in this conversation.\n")
                return
        elif argument.isdigit():
            turn=int(argument)
        else:
            print("Usage: /context [n]\n")
            return

        reply_id=db.get_reply_id(conversation_id,turn)
        if reply_id is None:
            print(f"No turn [{turn}] in this conversation.\n")
            return
        snap=db.get_snapshot(reply_id)
        if snap is None:
            print(f"No context recorded for [{turn}] (before snapshots existed).\n")
            return
        print(format_snapshot(snap,turn))

    elif command=="/help":
        print(HELP_TEXT+"\n")

    else:
        print(f"Unknown command: {command}. Try /help\n")
   
        
if __name__ == "__main__":
    db.init_db()

    conversations = db.list_conversations()

    if conversations:
        print_conversation_menu(conversations)
        choice = input("\nResume a conversation (enter a number), or press Enter to start new: ").strip()
    else:
        choice = ""

    if choice.isdigit() and 1 <= int(choice) <= len(conversations):
        conversation_id = conversations[int(choice) - 1]["id"]
    else:
        conversation_id = db.create_conversation()

    count = len(db.get_messages(conversation_id))

    print(f"\nKAMI chat (V1) — conversation #{conversation_id} - model: {MODEL}. Type 'exit' or 'quit' to stop.\n")
    if count!=0:
        print(f"(Loaded {count} previous messages.)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Exiting.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            handle_command(user_input,conversation_id)
            continue

        ctx=build_context(conversation_id,pending_user_message=user_input)
        payload_messages=render(ctx)

        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL,
                  "messages": payload_messages,
                  "stream": False,
                  "think": THINK,
                  "options": OLLAMA_OPTIONS,
                  },
                  timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        reply = data["message"]["content"]

        if not reply.strip():
            print("[warning: got an empty reply from Ollama — not saving this turn]\n")
            continue

        db.add_turn(conversation_id,user_input,reply,snapshot={
            "system_prompt":ctx["system"] if ctx["memories"] else None,
            "memories":ctx["memories"],
            "messages":ctx["messages"],
            "payload":payload_messages,
            "model":MODEL,
            "options":{"think":THINK,**OLLAMA_OPTIONS}
        })
        print(f"Assistant [{db.count_turns(conversation_id)}]: {reply}\n")