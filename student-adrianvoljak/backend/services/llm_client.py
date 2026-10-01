import os

import requests


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b",
)


def ask_llm(system_prompt, user_prompt, response_schema=None):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "stream": False,
        "options": {"temperature": 0},
    }

    if response_schema is not None:
        payload["format"] = response_schema

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    return response.json()["message"]["content"]