import requests

import db

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"

db.init_db()

latest_id = db.get_latest_conversation_id()
if latest_id is None:
    conversation_id = db.create_conversation()
else:
    choice = input(f"Resume conversation #{latest_id}? [Y/n] ").strip().lower()
    if choice in ("", "y", "yes"):
        conversation_id = latest_id
    else:
        conversation_id = db.create_conversation()

messages = db.get_messages(conversation_id)

print(f"KAMI chat (V1) — conversation #{conversation_id}. Type 'exit' or 'quit' to stop.\n")
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
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False
        }
    )
    data = response.json()
    reply = data["message"]["content"]

    if not reply.strip():
        print("[warning: got an empty reply from Ollama — not saving this turn]\n")
        continue

    messages.append({"role": "assistant", "content": reply})
    db.add_message(conversation_id, "assistant", reply)

    print(f"Assistant: {reply}\n")