import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"

messages = []

print("KAMI chat (V1) — type 'exit' or 'quit' to stop.\n")

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
    messages.append({"role": "assistant", "content": reply})

    print(f"Assistant: {reply}\n")