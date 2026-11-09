import db
import service
from datetime import datetime,timezone
from memory import (
    add_memory,list_memories,deactivate_memory,
    list_pending,accept_candidate,reject_candidate
)
from context import turn_labels,format_snapshot,format_changes
from errors import ServiceError
from config import MODEL


HELP_TEXT="""Commands:
  /remember [here] <text>  Store a memory (here = this conversation only)
  /memories                List memories visible here
  /forget <id>             Forget a memory
  /extract                 Suggest memories from this conversation
  /pending                 List suggestions waiting for a decision
  /accept <id> [here]      Save a suggestion (here = this conversation only)
  /reject <id>             Discard a suggestion
  /context [n]             Show what the model saw for reply n (default: latest)
  /exclude <n>             Keep turn n out of the model's context
  /include <n>             Put turn n back into context
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
        elif deactivate_memory(int(argument)):
           print(f"Forgot memory #{argument}\n")
        else:
            print(f"No active memory with id {argument}\n")

    elif command=="/extract":
        print("Extracting...",flush=True)
        try:
            found=service.extract_memories(conversation_id)
        except ServiceError as e:
            print(f"{e}\n")
            return

        if not found:
            print("No new memories suggested.\n")
            return

        print("Suggested memories:")
        for c in found:
            print(f" [{c['id']}] {c['content']}")
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
            turn=None
        elif argument.isdigit():
            turn=int(argument)
        else:
            print("Usage: /context [n]\n")
            return

        try:
            result=service.get_turn_context(conversation_id,turn)
        except ServiceError as e:
            print(f"{e}\n")
            return

        turn=result["turn"]
        labels=turn_labels(conversation_id)
        print(format_snapshot(result["snapshot"],turn,labels))
        if turn==1:
            print("-- Changed since previous --\n (first turn, nothing to compare)\n")
        elif result["diff"] is None:
            print(f"-- Changed since [{turn-1}] --\n (previous context not recorded)\n")
        else:
            print(format_changes(result["diff"],labels,turn-1))

    elif command in ("/exclude","/include"):
        if not argument.isdigit():
            print(f"Usage: {command} <n>\n")
            return
        turn=int(argument)
        excluding=command=="/exclude"

        try:
            changed=service.set_exclusion(conversation_id,turn,excluding)
        except ServiceError as e:
            print(f"{e}\n")
            return

        if excluding:
            print(f"Excluded [{turn}] from context, starting with your next message.\n" if changed
                  else f"[{turn}] is already excluded.\n")
        else:
            print(f"Included [{turn}] from context, starting with your next message.\n" if changed
                  else f"[{turn}] is not excluded.\n")
        
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

        try:
            result=service.send_message(conversation_id,user_input)
        except ServiceError as e:
            print(f"[error: {e}]\n")
            continue

        print(f"Assistant [{result['turn']}]: {result['reply']}\n")
