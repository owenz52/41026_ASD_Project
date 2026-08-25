import os

from dotenv import load_dotenv

load_dotenv()


def get_cfg(name, default):
    return os.getenv(name, default)


BACKEND_PORT = int(get_cfg("BACKEND_PORT", 5003))
DATABASE_SERVICE_URL = get_cfg("DATABASE_SERVICE_URL", "http://notebook-database:5004")
OLLAMA_BASE_URL = get_cfg("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = get_cfg("OLLAMA_MODEL", "qwen2.5:0.5b")
