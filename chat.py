import requests

import db
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"


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