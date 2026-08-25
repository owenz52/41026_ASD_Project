import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL


def ask_llm(system_prompt, user_prompt):
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]
