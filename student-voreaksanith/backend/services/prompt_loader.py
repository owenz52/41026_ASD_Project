from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _find_prompt_dir():
    """Locate the prompts folder, whichever layout the image was built with.

    Normally prompts/ sits beside backend/. Searching a few plausible
    locations instead of assuming one means a change to the Dockerfile cannot
    silently break every AI feature at runtime.
    """
    candidates = [
        BASE_DIR.parent / "prompts",   # /app/prompts   (backend at /app/backend)
        BASE_DIR / "prompts",          # /app/prompts   (backend flattened to /app)
        Path("/app/prompts"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


PROMPT_DIR = _find_prompt_dir()


def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()


def render_prompt(filename, **kwargs):
    text = load_prompt(filename)
    for key, value in kwargs.items():
        text = text.replace("{{" + key.upper() + "}}", str(value))
    return text
