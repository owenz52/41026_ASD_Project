from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR.parent
PROMPT_DIR = APP_DIR / "prompts"

def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()
