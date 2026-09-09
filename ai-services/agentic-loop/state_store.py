import json
from pathlib import Path


BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "data" / "state.json"


def load_reviewed_runs():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

        return set(
            data.get("reviewed_run_ids", [])
        )

    except Exception:
        return set()


def save_reviewed_runs(run_ids):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    STATE_FILE.write_text(
        json.dumps(
            {
                "reviewed_run_ids": sorted(run_ids)
            },
            indent=2,
        ),
        encoding="utf-8",
    )