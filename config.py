import os

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = os.environ.get("KAMI_MODEL", "qwen3.5:4b")
THINK = False
OLLAMA_OPTIONS = {"num_ctx": 8192}