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
    "ASSESSMENT_SERVICE_URL", "http://assessment-database:5008"
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


# ---------------------------------------------------------- Release 1

# Shared MCP server. Speaks the MCP protocol over streamable HTTP, with the
# JSON-RPC endpoint mounted at /mcp. It is not containerised, so from inside a
# container it is reached on the host in the same way as Ollama.
MCP_SERVER_URL = get_cfg("MCP_SERVER_URL", "http://host.docker.internal:8011")
MCP_PATH = get_cfg("MCP_PATH", "/mcp")
MCP_TIMEOUT_SECONDS = int(get_cfg("MCP_TIMEOUT_SECONDS", 30))

# Shared RAG server. Stateless: the calling feature supplies the documents to
# search, so the calendar builds chunks from its own events.
RAG_SERVER_URL = get_cfg("RAG_SERVER_URL", "http://host.docker.internal:8012")
RAG_TIMEOUT_SECONDS = int(get_cfg("RAG_TIMEOUT_SECONDS", 90))
RAG_TOP_K = int(get_cfg("RAG_TOP_K", 5))

# The shared server accepts at most 100 documents, each at most 2000
# characters, so the calendar caps what it sends.
RAG_MAX_DOCUMENTS = int(get_cfg("RAG_MAX_DOCUMENTS", 100))
RAG_MAX_CHARS = int(get_cfg("RAG_MAX_CHARS", 2000))

# The feature name the shared RAG server scopes documents by. It must match
# [a-z][a-z0-9_-]{1,31}.
RAG_FEATURE = get_cfg("RAG_FEATURE", "calendar")


def _flag(name, default="1"):
    return get_cfg(name, default) not in ("0", "false", "False", "no")


# Retained in the code but switched off during CI, where the shared servers
# are not running.
MCP_ENABLED = _flag("MCP_ENABLED")
RAG_ENABLED = _flag("RAG_ENABLED")
