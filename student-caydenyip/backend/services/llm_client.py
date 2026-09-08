import os

from openai import OpenAI



OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")


def create_chat_completion(messages, max_tokens=300, temperature=0, model=None):
    response = client.chat.completions.create(
        model=model or OLLAMA_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


