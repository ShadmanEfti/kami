import json
import requests
from config import OLLAMA_URL,MODEL

TRANSCRIPT_WINDOW=6
MAX_CANDIDATES=5
REQUEST_TIMEOUT=120

class ExtractionError(Exception):
    pass

EXTRACTION_SCHEMA={
    "type": "object",
    "properties":{"memories":{"type":"array","items":{"type":"string"}}},
    "required":["memories"],
}

SYSTEM_PROMPT="""You extract long-term memories about the user from a conversation transcript.
 
A memory is a durable fact the user stated about themselves: identity, background, ongoing projects, stable preferences, or constraints that will still be true in future conversations.
 
Rules:
- Only extract what the user explicitly said. Never infer or guess.
- Write each memory as one short sentence starting with "User", e.g. "User's name is Sultana." or "User prefers Python over R."
- Skip temporary states (moods, today's plans), questions, requests for help, and small talk.
- Skip anything already listed under Existing memories.
- If nothing is worth remembering, return an empty list.
 
Respond only with JSON: {"memories": [...]}"""

def normalize(text):
    return text.strip().casefold().rstrip(".").strip()

def build_user_message(user_messages,existing):

    existing_block="\n".join(f"- {e}" for e in existing) if existing else "(none)"
    transcript="\n".join(f"User: {m}" for m in user_messages[-TRANSCRIPT_WINDOW:])
    return f"Existing memories:\n{existing_block}\n\nTranscript:\n{transcript}"

def extract_candidates(user_messages,existing):

    if not user_messages:
        return []

    payload={
        "model":MODEL,
        "messages":[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":build_user_message(user_messages,existing)},
        ],
        "stream":False,
        "format":EXTRACTION_SCHEMA,
        "options":{"temperature":0},
    }

    try:
        response=requests.post(OLLAMA_URL,json=payload,timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content=response.json()["message"]["content"]
        parsed=json.loads(content)

    except requests.ConnectionError as e:
        raise ExtractionError("Can't reach Ollama. Is it running?") from e

    except requests.Timeout as e:
        raise ExtractionError(f"Ollama took longer than {REQUEST_TIMEOUT}s to answer") from e

    except requests.RequestException as e:
        raise ExtractionError(f"Request to Ollama failed: {e}") from e

    except (KeyError,TypeError,ValueError) as e:
        raise ExtractionError(f"Unexpected response from the model: {e}") from e

    if not isinstance(parsed,dict) or not isinstance(parsed.get("memories",[]),list):
        raise ExtractionError("Model returned JSON in the wrong shape")

    seen={normalize(m) for m in existing}
    candidates=[]

    for item in parsed.get("memories",[]):

        if not isinstance(item,str):
            continue

        text=item.strip()
        key=normalize(text)

        if not key or key in seen:
            continue

        seen.add(key)
        candidates.append(text)

        if len(candidates)==MAX_CANDIDATES:
            break

    return candidates
    