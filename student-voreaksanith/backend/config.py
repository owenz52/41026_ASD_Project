import os

from dotenv import load_dotenv

load_dotenv()


def get_cfg(name, default):
    return os.getenv(name, default)


BACKEND_PORT = int(get_cfg("BACKEND_PORT", 5005))

# The calendar's own database service.
DATABASE_SERVICE_URL = get_cfg(
    "DATABASE_SERVICE_URL", "http://calendar-database:5006"
)


# Read-only sources the calendar pulls deadlines from. Both are other teams'
# database services; the calendar only ever performs GETs against them and
# keeps working if either is unavailable.
ASSESSMENT_SERVICE_URL = get_cfg(
    "ASSESSMENT_SERVICE_URL", "http://priority-database:5008"
)

EXAM_SERVICE_URL = get_cfg(
    "EXAM_SERVICE_URL", "http://exam-database:5010"
)


OLLAMA_BASE_URL = get_cfg("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = get_cfg("OLLAMA_MODEL", "qwen2.5:0.5b")

OLLAMA_TIMEOUT_SECONDS = int(get_cfg("OLLAMA_TIMEOUT_SECONDS", 30))

AGENT_HORIZON_DAYS = int(get_cfg("AGENT_HORIZON_DAYS", 21))
AGENT_SESSION_MINUTES = int(get_cfg("AGENT_SESSION_MINUTES", 90))
AGENT_STUDY_START_HOUR = int(get_cfg("AGENT_STUDY_START_HOUR", 9))
AGENT_STUDY_END_HOUR = int(get_cfg("AGENT_STUDY_END_HOUR", 21))
AGENT_MAX_SUGGESTIONS = int(get_cfg("AGENT_MAX_SUGGESTIONS", 4))
AGENT_MAX_CANDIDATE_SLOTS = int(get_cfg("AGENT_MAX_CANDIDATE_SLOTS", 12))
