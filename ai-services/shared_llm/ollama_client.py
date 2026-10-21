
import os

import requests


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:0.5b"


class OllamaClient:
    def __init__(self, base_url=None, model=None):
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")

        self.model = model or os.getenv(
            "OLLAMA_MODEL", DEFAULT_MODEL
        )

    def generate(self, prompt, model=None, timeout=120):
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model or self.model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=timeout,
        )

        response.raise_for_status()

        return response.json().get("response", "").strip()

    def chat(
        self,
        system_prompt,
        user_prompt,
        response_schema=None,
        model=None,
        timeout=60,
    ):
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }

        if response_schema is not None:
            payload["format"] = response_schema

        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=timeout,
        )

        response.raise_for_status()

        return response.json()["message"]["content"]
