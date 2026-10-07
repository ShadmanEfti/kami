import requests
import db
from datetime import datetime
from memory import (
    add_memory,list_memories,deactivate_memory,get_active_memories,
    add_candidate,list_pending,accept_candidate,reject_candidate,list_rejected
)
from extractor import extract_candidates,ExtractionError
from config import OLLAMA_URL,MODEL


HELP_TEXT="""Commands:
  /remember <text> Store a memory
  /memories List stored memories
  /forget <id> Forget a memory
  /help Show this message"""


def print_conversation_menu(conversations):

    for i, c in enumerate(conversations, start=1):
        ts = datetime.strptime(c["created_at"], "%Y-%m-%d %H:%M:%S")
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
                print(f" [{m['id']}] {m['content']}")
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

    elif command=="/help":
        print(HELP_TEXT+"\n")

    else:
        print(f"Unknown command: {command}. Try /help\n")


def build_system_prompt(memories):

    if not memories:
        return None
    lines="\n".join(f"- {m['content']}" for m in memories)
    return f"You are a helpful assistant.\n\nKnown facts about the user:\n{lines}"

        
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

    messages = db.get_messages(conversation_id)

    print(f"\nKAMI chat (V1) — conversation #{conversation_id}. Type 'exit' or 'quit' to stop.\n")
    if messages:
        print(f"(Loaded {len(messages)} previous messages.)\n")

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

        messages.append({"role": "user", "content": user_input})
        db.add_message(conversation_id, "user", user_input)

        active=get_active_memories(conversation_id)
        system_prompt=build_system_prompt(active)
        if system_prompt is None:
            payload_messages=messages
        else:
            payload_messages=[{"role":"system","content":system_prompt}]+messages

        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": payload_messages, "stream": False}
        )
        data = response.json()
        reply = data["message"]["content"]

        if not reply.strip():
            print("[warning: got an empty reply from Ollama — not saving this turn]\n")
            continue

        messages.append({"role": "assistant", "content": reply})
        db.add_message(conversation_id, "assistant", reply)

        print(f"Assistant: {reply}\n")