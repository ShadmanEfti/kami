import requests
import db
from datetime import datetime
from memory import add_memory, list_memories, deactivate_memory

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"

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


def handle_command(user_input,conversation_id):

    parts=user_input.split(maxsplit=1)
    command=parts[0].lower()
    argument=parts[1] if len(parts)>1 else ""

    if command=="/remember":
        try:
            memory_id=add_memory(argument)
            print(f"Remembered (#{memory_id})\n")
        except ValueError as e:
            print(f"Error: {e}\n")

    elif command=="/memories":
        memories=list_memories()
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

        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": messages, "stream": False}
        )
        data = response.json()
        reply = data["message"]["content"]

        if not reply.strip():
            print("[warning: got an empty reply from Ollama — not saving this turn]\n")
            continue

        messages.append({"role": "assistant", "content": reply})
        db.add_message(conversation_id, "assistant", reply)

        print(f"Assistant: {reply}\n")