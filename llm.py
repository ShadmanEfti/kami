import requests
from config import OLLAMA_URL,MODEL,THINK,OLLAMA_OPTIONS
from errors import ModelUnavailable

TIMEOUT=120

def call_model(payload_messages):
    try:
        response=requests.post(
            OLLAMA_URL,
            json={
                "model":MODEL,
                "messages":payload_messages,
                "stream":False,
                "think":THINK,
                "options":OLLAMA_OPTIONS,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ModelUnavailable(
            f"Could not reach the model ({e.__class__.__name__}). Nothing was saved; try again."
        )from e
    except ValueError as e:
        raise ModelUnavailable("Model returned an invalid response. Nothing was saved.") from e
