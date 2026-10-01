import json
import os
import sqlite3
import time
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import requests
from llm_client import create_chat_completion


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR.parent

REPORTS_DIR = APP_DIR / "reports"
CORPUS_PATH = BASE_DIR / "corpus" / "corpus.jsonl"
AUDIT_PATH = BASE_DIR / "rag-audit.jsonl"
CHROMA_PATH = BASE_DIR / "chroma"

DATABASE_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://exam-database:5010",
)

DB_PATH_CANDIDATES = [
    BASE_DIR.parent / "data" / "exam.db",
]

REPORT_FILES = [
    "report.json",
    "run-report.md",
    "integration-report.md",
    "tool-review.md",
    "boundary-analysis.md",
]

COLLECTION_NAME = "student_enrolment_enterprise_context"

EMBED_VECTOR_SIZE = 256

_collection = None

_last_corpus_chunks: list[dict[str, Any]] = []


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_db_path() -> Path:
    for path in DB_PATH_CANDIDATES:
        if path.exists():
            return path

    return DB_PATH_CANDIDATES[0]


# ============================================================
# EMBEDDINGS
# ============================================================

def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []

    for text in texts:

        values = [0.0] * EMBED_VECTOR_SIZE
        tokens = (text or "").lower().split()

        if not tokens:
            vectors.append(values)
            continue

        for token in tokens:

            digest = hashlib.sha256(
                token.encode("utf-8")
            ).digest()

            for i, byte in enumerate(digest):

                idx = i % EMBED_VECTOR_SIZE

                values[idx] += (
                    byte / 255.0
                ) - 0.5

        norm = sum(
            value * value
            for value in values
        ) ** 0.5

        if norm > 0:

            values = [
                value / norm
                for value in values
            ]

        vectors.append(values)

    return vectors


# ============================================================
# CHROMA
# ============================================================

def get_collection():
    global _collection

    if _collection is None:

        client = chromadb.PersistentClient(
            path=str(CHROMA_PATH)
        )

        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME
        )

    return _collection


def reset_collection() -> None:
    global _collection

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    try:
        client.delete_collection(
            name=COLLECTION_NAME
        )
    except Exception:
        pass

    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )


# ============================================================
# AUDIT LOGGING
# ============================================================

def append_audit(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: dict[str, Any],
    validation_status: str,
    outcome: str,
    start_time: float,
) -> None:

    AUDIT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    duration_ms = int(
        (time.time() - start_time) * 1000
    )

    record = {
        "request_id": str(uuid.uuid4()),
        "trace_id": str(uuid.uuid4()),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_output": tool_output,
        "timestamp": now_iso(),
        "duration_ms": duration_ms,
        "validation_status": validation_status,
        "outcome": outcome,
    }

    with AUDIT_PATH.open(
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            json.dumps(record) + "\n"
        )


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text: str,
    max_words: int = 80,
) -> list[str]:

    words = text.split()

    if not words:
        return []

    chunks = []

    for i in range(
        0,
        len(words),
        max_words,
    ):

        chunk = " ".join(
            words[
                i:i + max_words
            ]
        ).strip()

        if chunk:
            chunks.append(chunk)

    return chunks


# ============================================================
# DATABASE CHUNKS
# ============================================================

def load_database_chunks() -> list[dict[str, Any]]:
    """
    Load both:

        course_exams
        student_exams

    from the SQLite database.
    """

    db_path = resolve_db_path()

    # --------------------------------------------------------
    # SQLITE DATABASE NOT AVAILABLE
    # --------------------------------------------------------

    if not db_path.exists():

        try:

            # ----------------------------------------------
            # COURSE EXAMS SERVICE
            # ----------------------------------------------

            response = requests.get(
                f"{DATABASE_SERVICE_URL}/course-exams",
                timeout=10,
            )

            response.raise_for_status()

            course_exams = response.json()

            chunks: list[dict[str, Any]] = []

            chunks.append(
                {
                    "chunk_id": (
                        "db_service_course_exam_count"
                    ),
                    "source_id": (
                        "database-service:/course-exams"
                    ),
                    "authority_tier": "tier_1",
                    "text": (
                        f"There are "
                        f"{len(course_exams)} course "
                        "exam records."
                    ),
                    "metadata": {
                        "source_type": (
                            "database_service"
                        ),
                        "table": "course_exams",
                        "metric": "count",
                    },
                    "indexed_at": now_iso(),
                }
            )

            for row in course_exams[:500]:

                course_exam_id = row.get(
                    "course_exam_id",
                    "unknown",
                )

                chunks.append(
                    {
                        "chunk_id": (
                            "db_service_course_exam_"
                            f"{course_exam_id}"
                        ),
                        "source_id": (
                            "database-service:/course-exams"
                        ),
                        "authority_tier": "tier_1",
                        "text": (
                            "Course exam record: "
                            f"course_exam_id="
                            f"{course_exam_id}, "
                            f"course_id="
                            f"{row.get('course_id', 'unknown')}, "
                            f"exam_name="
                            f"{row.get('exam_name', 'unknown')}, "
                            f"exam_date="
                            f"{row.get('exam_date', 'unknown')}, "
                            f"exam_time="
                            f"{row.get('exam_time', 'unknown')}."
                        ),
                        "metadata": {
                            "source_type": (
                                "database_service"
                            ),
                            "table": "course_exams",
                        },
                        "indexed_at": now_iso(),
                    }
                )

            # ----------------------------------------------
            # STUDENT EXAMS SERVICE
            # ----------------------------------------------

            try:

                response = requests.get(
                    f"{DATABASE_SERVICE_URL}/student-exams",
                    timeout=10,
                )

                response.raise_for_status()

                student_exams = response.json()

                chunks.append(
                    {
                        "chunk_id": (
                            "db_service_student_exam_count"
                        ),
                        "source_id": (
                            "database-service:/student-exams"
                        ),
                        "authority_tier": "tier_1",
                        "text": (
                            f"There are "
                            f"{len(student_exams)} student "
                            "exam records."
                        ),
                        "metadata": {
                            "source_type": (
                                "database_service"
                            ),
                            "table": "student_exams",
                            "metric": "count",
                        },
                        "indexed_at": now_iso(),
                    }
                )

                for row in student_exams[:500]:

                    exam_id = row.get(
                        "exam_id",
                        "unknown",
                    )

                    chunks.append(
                        {
                            "chunk_id": (
                                "db_service_student_exam_"
                                f"{exam_id}"
                            ),
                            "source_id": (
                                "database-service:/student-exams"
                            ),
                            "authority_tier": "tier_1",
                            "text": (
                                "Student exam record: "
                                f"exam_id={exam_id}, "
                                f"course_exam_id="
                                f"{row.get('course_exam_id', 'unknown')}, "
                                f"course_id="
                                f"{row.get('course_id', 'unknown')}, "
                                f"student_id="
                                f"{row.get('student_id', 'unknown')}, "
                                f"exam_name="
                                f"{row.get('exam_name', 'unknown')}, "
                                f"exam_date="
                                f"{row.get('exam_date', 'unknown')}, "
                                f"exam_time="
                                f"{row.get('exam_time', 'unknown')}, "
                                f"status="
                                f"{row.get('status', 'unknown')}."
                            ),
                            "metadata": {
                                "source_type": (
                                    "database_service"
                                ),
                                "table": "student_exams",
                            },
                            "indexed_at": now_iso(),
                        }
                    )

            except Exception:
                pass

            return chunks

        except Exception as exc:

            return [
                {
                    "chunk_id": "db_missing",
                    "source_id": str(db_path),
                    "authority_tier": "tier_1",
                    "text": (
                        f"Database file not found: "
                        f"{db_path}. "
                        f"Database-service fallback failed: "
                        f"{exc}"
                    ),
                    "metadata": {
                        "source_type": "database",
                        "exists": False,
                    },
                    "indexed_at": now_iso(),
                }
            ]

    # --------------------------------------------------------
    # OPEN DATABASE
    # --------------------------------------------------------

    conn = sqlite3.connect(
        db_path
    )

    conn.row_factory = sqlite3.Row

    chunks: list[dict[str, Any]] = []

    try:

        # ----------------------------------------------------
        # TABLES
        # ----------------------------------------------------

        tables = [
            row["name"]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()
        ]

        chunks.append(
            {
                "chunk_id": "db_schema",
                "source_id": str(db_path),
                "authority_tier": "tier_1",
                "text": (
                    "Database contains the following tables: "
                    f"{', '.join(tables)}."
                ),
                "metadata": {
                    "source_type": "database",
                    "tables": tables,
                },
                "indexed_at": now_iso(),
            }
        )

        # ====================================================
        # COURSE EXAMS
        # ====================================================

        if "course_exams" in tables:

            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM course_exams
                """
            ).fetchone()

            count = (
                row["count"]
                if row
                else 0
            )

            chunks.append(
                {
                    "chunk_id": (
                        "db_course_exam_count"
                    ),
                    "source_id": str(db_path),
                    "authority_tier": "tier_1",
                    "text": (
                        f"There are {count} course exam "
                        "records in the course_exams table."
                    ),
                    "metadata": {
                        "source_type": "database",
                        "table": "course_exams",
                        "metric": "count",
                    },
                    "indexed_at": now_iso(),
                }
            )

            rows = conn.execute(
                """
                SELECT
                    course_exam_id,
                    course_id,
                    exam_name,
                    exam_date,
                    exam_time
                FROM course_exams
                ORDER BY course_exam_id
                """
            ).fetchall()

            for row in rows:

                r = dict(row)

                chunks.append(
                    {
                        "chunk_id": (
                            f"db_course_exam_"
                            f"{r['course_exam_id']}"
                        ),
                        "source_id": str(db_path),
                        "authority_tier": "tier_1",
                        "text": (
                            "Course exam record: "
                            f"course_exam_id="
                            f"{r['course_exam_id']}, "
                            f"course_id="
                            f"{r['course_id']}, "
                            f"exam_name="
                            f"{r['exam_name']}, "
                            f"exam_date="
                            f"{r['exam_date']}, "
                            f"exam_time="
                            f"{r['exam_time']}."
                        ),
                        "metadata": {
                            "source_type": "database",
                            "table": "course_exams",
                            "course_exam_id": (
                                r["course_exam_id"]
                            ),
                            "course_id": (
                                r["course_id"]
                            ),
                        },
                        "indexed_at": now_iso(),
                    }
                )

        # ====================================================
        # STUDENT EXAMS
        # ====================================================

        if "student_exams" in tables:

            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM student_exams
                WHERE is_deleted = 0
                """
            ).fetchone()

            count = (
                row["count"]
                if row
                else 0
            )

            chunks.append(
                {
                    "chunk_id": (
                        "db_student_exam_count"
                    ),
                    "source_id": str(db_path),
                    "authority_tier": "tier_1",
                    "text": (
                        f"There are {count} active "
                        "student exam records in the "
                        "student_exams table."
                    ),
                    "metadata": {
                        "source_type": "database",
                        "table": "student_exams",
                        "metric": "active_count",
                    },
                    "indexed_at": now_iso(),
                }
            )

            rows = conn.execute(
                """
                SELECT
                    exam_id,
                    course_exam_id,
                    course_id,
                    student_id,
                    exam_name,
                    exam_date,
                    exam_time,
                    status,
                    is_deleted
                FROM student_exams
                WHERE is_deleted = 0
                ORDER BY
                    student_id,
                    exam_date,
                    exam_time
                """
            ).fetchall()

            for row in rows:

                r = dict(row)

                chunks.append(
                    {
                        "chunk_id": (
                            f"db_student_exam_"
                            f"{r['exam_id']}"
                        ),
                        "source_id": str(db_path),
                        "authority_tier": "tier_1",
                        "text": (
                            "Student exam record: "
                            f"exam_id="
                            f"{r['exam_id']}, "
                            f"course_exam_id="
                            f"{r['course_exam_id']}, "
                            f"course_id="
                            f"{r['course_id']}, "
                            f"student_id="
                            f"{r['student_id']}, "
                            f"exam_name="
                            f"{r['exam_name']}, "
                            f"exam_date="
                            f"{r['exam_date']}, "
                            f"exam_time="
                            f"{r['exam_time']}, "
                            f"status="
                            f"{r['status']}."
                        ),
                        "metadata": {
                            "source_type": "database",
                            "table": "student_exams",
                            "exam_id": r["exam_id"],
                            "course_exam_id": (
                                r["course_exam_id"]
                            ),
                            "course_id": (
                                r["course_id"]
                            ),
                            "student_id": (
                                r["student_id"]
                            ),
                            "status": r["status"],
                        },
                        "indexed_at": now_iso(),
                    }
                )

        # ====================================================
        # JOIN BOTH TABLES
        # ====================================================

        if (
            "student_exams" in tables
            and "course_exams" in tables
        ):

            rows = conn.execute(
                """
                SELECT
                    se.exam_id,
                    se.student_id,
                    se.course_id,
                    se.course_exam_id,

                    se.exam_name AS student_exam_name,
                    se.exam_date AS student_exam_date,
                    se.exam_time AS student_exam_time,

                    se.status,

                    ce.exam_name AS course_exam_name,
                    ce.exam_date AS course_exam_date,
                    ce.exam_time AS course_exam_time

                FROM student_exams AS se

                LEFT JOIN course_exams AS ce
                    ON se.course_exam_id =
                       ce.course_exam_id

                WHERE se.is_deleted = 0

                ORDER BY
                    se.student_id,
                    se.exam_date,
                    se.exam_time
                """
            ).fetchall()

            for row in rows:

                r = dict(row)

                chunks.append(
                    {
                        "chunk_id": (
                            "db_student_exam_join_"
                            f"{r['exam_id']}"
                        ),
                        "source_id": str(db_path),
                        "authority_tier": "tier_1",
                        "text": (
                            "Student exam assignment: "
                            f"student_id="
                            f"{r['student_id']}, "
                            f"course_id="
                            f"{r['course_id']}, "
                            f"course_exam_id="
                            f"{r['course_exam_id']}, "
                            f"exam_id="
                            f"{r['exam_id']}, "
                            f"exam_name="
                            f"{r['student_exam_name']}, "
                            f"exam_date="
                            f"{r['student_exam_date']}, "
                            f"exam_time="
                            f"{r['student_exam_time']}, "
                            f"status="
                            f"{r['status']}. "
                            "Course exam template: "
                            f"exam_name="
                            f"{r['course_exam_name']}, "
                            f"exam_date="
                            f"{r['course_exam_date']}, "
                            f"exam_time="
                            f"{r['course_exam_time']}."
                        ),
                        "metadata": {
                            "source_type": (
                                "database_join"
                            ),
                            "tables": [
                                "student_exams",
                                "course_exams",
                            ],
                            "exam_id": r["exam_id"],
                            "student_id": (
                                r["student_id"]
                            ),
                            "course_id": (
                                r["course_id"]
                            ),
                            "course_exam_id": (
                                r["course_exam_id"]
                            ),
                        },
                        "indexed_at": now_iso(),
                    }
                )

    finally:

        conn.close()

    return chunks


# ============================================================
# REPORT CHUNKS
# ============================================================

def load_report_chunks() -> list[dict[str, Any]]:

    chunks: list[dict[str, Any]] = []

    for name in REPORT_FILES:

        path = REPORTS_DIR / name

        if not path.exists():
            continue

        text = ""

        try:

            if path.suffix == ".json":

                text = json.dumps(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    ),
                    indent=2,
                )

            else:

                text = path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

        except Exception:

            text = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        for i, chunk in enumerate(
            chunk_text(text),
            start=1,
        ):

            chunks.append(
                {
                    "chunk_id": (
                        f"{path.stem}_{i}"
                    ),
                    "source_id": (
                        f"reports/{name}"
                    ),
                    "authority_tier": "tier_2",
                    "text": chunk,
                    "metadata": {
                        "source_type": "report",
                        "file": name,
                    },
                    "indexed_at": now_iso(),
                }
            )

    return chunks


# ============================================================
# REPOSITORY CHUNKS
# ============================================================

def load_repository_chunks() -> list[dict[str, Any]]:

    ignored = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "chroma",
    }

    files: list[str] = []

    for root, dirs, filenames in os.walk(
        APP_DIR,
        topdown=True,
        followlinks=False,
        onerror=lambda e: None,
    ):

        pruned_dirs: list[str] = []

        for directory_name in dirs:

            if directory_name in ignored:
                continue

            directory_path = (
                Path(root)
                / directory_name
            )

            try:

                if directory_path.is_symlink():
                    continue

            except OSError:

                continue

            pruned_dirs.append(
                directory_name
            )

        dirs[:] = pruned_dirs

        for filename in filenames:

            file_path = (
                Path(root)
                / filename
            )

            try:

                if file_path.is_symlink():
                    continue

                rel = file_path.relative_to(
                    APP_DIR
                )

                files.append(
                    str(rel).replace(
                        "\\",
                        "/",
                    )
                )

            except (
                OSError,
                ValueError,
            ):

                continue

    text = (
        "Repository files include: "
        + ", ".join(
            sorted(files[:400])
        )
    )

    return [
        {
            "chunk_id": "repo_index",
            "source_id": "repository",
            "authority_tier": "tier_3",
            "text": text,
            "metadata": {
                "source_type": "repository",
                "file_count": len(files),
            },
            "indexed_at": now_iso(),
        }
    ]


# ============================================================
# CORPUS
# ============================================================

def build_corpus() -> list[dict[str, Any]]:

    chunks: list[dict[str, Any]] = []

    chunks.extend(
        load_database_chunks()
    )

    chunks.extend(
        load_report_chunks()
    )

    chunks.extend(
        load_repository_chunks()
    )

    return chunks


def write_corpus(
    chunks: list[dict[str, Any]]
) -> None:

    CORPUS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with CORPUS_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:

        for chunk in chunks:

            f.write(
                json.dumps(chunk)
                + "\n"
            )


def read_corpus() -> list[dict[str, Any]]:

    if not CORPUS_PATH.exists():
        return []

    chunks: list[dict[str, Any]] = []

    with CORPUS_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            try:

                chunks.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:

                continue

    return chunks


# ============================================================
# LEXICAL FALLBACK
# ============================================================

def lexical_fallback_retrieve(
    query: str,
    k: int,
) -> list[dict[str, Any]]:

    corpus = (
        _last_corpus_chunks
        or read_corpus()
    )

    query_tokens = set(
        (query or "")
        .lower()
        .split()
    )

    tier_weight = {
        "tier_1": 3,
        "tier_2": 2,
        "tier_3": 1,
    }

    scored = []

    for chunk in corpus:

        text = chunk.get(
            "text",
            "",
        )

        text_tokens = set(
            text.lower().split()
        )

        overlap = len(
            query_tokens.intersection(
                text_tokens
            )
        )

        scored.append(
            {
                "rank": 0,
                "chunk_id": chunk.get(
                    "chunk_id"
                ),
                "source_id": chunk.get(
                    "source_id"
                ),
                "authority_tier": chunk.get(
                    "authority_tier"
                ),
                "distance": None,
                "text": text,
                "_score": overlap,
            }
        )

    scored.sort(
        key=lambda r: (
            tier_weight.get(
                r.get(
                    "authority_tier"
                ),
                0,
            ),
            r.get(
                "_score",
                0,
            ),
        ),
        reverse=True,
    )

    top = scored[
        :max(k, 1)
    ]

    for i, row in enumerate(
        top,
        start=1,
    ):

        row["rank"] = i

        row.pop(
            "_score",
            None,
        )

    return top


# ============================================================
# REFRESH CORPUS
# ============================================================

def refresh_corpus(
    caller: str = "student",
) -> dict[str, Any]:

    global _last_corpus_chunks

    start = time.time()

    try:

        chunks = build_corpus()

        _last_corpus_chunks = chunks

        write_corpus(chunks)

        vector_store_status = "ready"
        vector_store_error = None

        try:

            reset_collection()

            collection = get_collection()

            if chunks:

                ids = [
                    c["chunk_id"]
                    for c in chunks
                ]

                docs = [
                    c["text"]
                    for c in chunks
                ]

                metas = [
                    {
                        "source_id": c[
                            "source_id"
                        ],
                        "authority_tier": c[
                            "authority_tier"
                        ],
                        "indexed_at": c[
                            "indexed_at"
                        ],
                    }
                    for c in chunks
                ]

                embeddings = embed_texts(
                    docs
                )

                collection.add(
                    ids=ids,
                    documents=docs,
                    metadatas=metas,
                    embeddings=embeddings,
                )

        except Exception as exc:

            vector_store_status = "degraded"
            vector_store_error = str(exc)

        output = {
            "status": "success",
            "caller": caller,
            "chunk_count": len(chunks),
            "collection": COLLECTION_NAME,
            "corpus_path": str(
                CORPUS_PATH
            ),
            "vector_store_status": (
                vector_store_status
            ),
        }

        if vector_store_error:

            output[
                "vector_store_error"
            ] = vector_store_error

        append_audit(
            "refresh_corpus",
            {
                "caller": caller
            },
            output,
            "pass",
            "corpus_refreshed",
            start,
        )

        return output

    except Exception as exc:

        output = {
            "status": "error",
            "error": str(exc),
        }

        append_audit(
            "refresh_corpus",
            {
                "caller": caller
            },
            output,
            "fail",
            "error",
            start,
        )

        return output


# ============================================================
# RETRIEVE CONTEXT
# ============================================================

def retrieve_context(
    query: str,
    k: int = 5,
    caller: str = "student",
) -> dict[str, Any]:

    start = time.time()

    try:

        retrieval_mode = "vector"
        ranked = []

        try:

            collection = get_collection()

            if collection.count() == 0:

                refreshed = refresh_corpus(
                    caller="auto_refresh"
                )

                if (
                    refreshed.get(
                        "status"
                    )
                    != "success"
                ):

                    raise RuntimeError(
                        "empty_collection"
                    )

            query_embedding = embed_texts(
                [query]
            )

            results = collection.query(
                query_embeddings=query_embedding,
                n_results=k,
            )

            ids = (
                results.get("ids")
                or [[]]
            )[0]

            docs = (
                results.get("documents")
                or [[]]
            )[0]

            metas = (
                results.get("metadatas")
                or [[]]
            )[0]

            distances = (
                results.get("distances")
                or [[]]
            )[0]

            for i, chunk_id in enumerate(
                ids
            ):

                row_meta = (
                    metas[i]
                    if (
                        i < len(metas)
                        and isinstance(
                            metas[i],
                            dict,
                        )
                    )
                    else {}
                )

                ranked.append(
                    {
                        "rank": i + 1,
                        "chunk_id": chunk_id,
                        "source_id": row_meta.get(
                            "source_id"
                        ),
                        "authority_tier": row_meta.get(
                            "authority_tier"
                        ),
                        "distance": (
                            distances[i]
                            if i < len(distances)
                            else None
                        ),
                        "text": (
                            docs[i]
                            if i < len(docs)
                            else ""
                        ),
                    }
                )

            tier_weight = {
                "tier_1": 3,
                "tier_2": 2,
                "tier_3": 1,
            }

            ranked.sort(
                key=lambda x: (
                    tier_weight.get(
                        x.get(
                            "authority_tier"
                        ),
                        0,
                    ),
                    -(
                        x.get(
                            "distance"
                        )
                        if isinstance(
                            x.get(
                                "distance"
                            ),
                            (
                                int,
                                float,
                            ),
                        )
                        else 1e9
                    ),
                ),
                reverse=True,
            )

        except Exception:

            retrieval_mode = (
                "lexical_fallback"
            )

            if (
                not _last_corpus_chunks
                and not CORPUS_PATH.exists()
            ):

                refreshed = refresh_corpus(
                    caller="auto_refresh"
                )

                if (
                    refreshed.get(
                        "status"
                    )
                    != "success"
                ):

                    return {
                        "status": "error",
                        "error": (
                            "corpus_unavailable"
                        ),
                    }

            ranked = lexical_fallback_retrieve(
                query,
                k,
            )

        output = {
            "status": "success",
            "query": query,
            "caller": caller,
            "k": k,
            "retrieval_mode": retrieval_mode,
            "results": ranked,
        }

        append_audit(
            "retrieve_context",
            {
                "query": query,
                "k": k,
                "caller": caller,
            },
            {
                "result_count": len(
                    ranked
                ),
                "chunk_ids": [
                    r["chunk_id"]
                    for r in ranked
                ],
            },
            "pass",
            "context_retrieved",
            start,
        )

        return output

    except Exception as exc:

        output = {
            "status": "error",
            "error": str(exc),
            "query": query,
        }

        append_audit(
            "retrieve_context",
            {
                "query": query,
                "k": k,
                "caller": caller,
            },
            output,
            "fail",
            "error",
            start,
        )

        return output


# ============================================================
# CONFIDENCE
# ============================================================

def confidence_from_results(
    results: list[dict[str, Any]]
) -> str:

    if not results:
        return "Unknown"

    tier_1 = sum(
        1
        for r in results
        if r.get(
            "authority_tier"
        ) == "tier_1"
    )

    tier_2 = sum(
        1
        for r in results
        if r.get(
            "authority_tier"
        ) == "tier_2"
    )

    if (
        tier_1 >= 2
        and len(results) >= 3
    ):

        return "High"

    if (
        tier_1 >= 1
        or tier_2 >= 2
    ):

        return "Medium"

    return "Low"


# ============================================================
# EXTRACT STUDENT EXAM RECORDS
# ============================================================

def extract_student_records(
    results: list[dict[str, Any]]
) -> list[dict[str, str]]:

    records: list[
        dict[str, str]
    ] = []

    for row in results:

        text = row.get(
            "text",
            "",
        )

        if (
            "Student exam record:"
            not in text
        ):

            continue

        payload = (
            text
            .split(
                "Student exam record:",
                1,
            )[1]
            .strip()
            .rstrip(".")
        )

        parts = [
            p.strip()
            for p in payload.split(",")
        ]

        values: dict[str, str] = {}

        for part in parts:

            if "=" not in part:
                continue

            key, value = part.split(
                "=",
                1,
            )

            values[
                key.strip()
            ] = value.strip()

        if values.get(
            "student_id"
        ):

            records.append(
                values
            )

    def key_fn(
        item: dict[str, str]
    ):

        sid = item.get(
            "student_id",
            "",
        )

        if sid.isdigit():

            return (
                0,
                int(sid),
            )

        return (
            1,
            sid,
        )

    records.sort(
        key=key_fn
    )

    return records


# ============================================================
# EXTRACT COURSE EXAM RECORDS
# ============================================================

def extract_course_exam_records(
    results: list[dict[str, Any]]
) -> list[dict[str, str]]:

    records: list[
        dict[str, str]
    ] = []

    for row in results:

        text = row.get(
            "text",
            "",
        )

        if (
            "Course exam record:"
            not in text
        ):

            continue

        payload = (
            text
            .split(
                "Course exam record:",
                1,
            )[1]
            .strip()
            .rstrip(".")
        )

        parts = [
            p.strip()
            for p in payload.split(",")
        ]

        values: dict[str, str] = {}

        for part in parts:

            if "=" not in part:
                continue

            key, value = part.split(
                "=",
                1,
            )

            values[
                key.strip()
            ] = value.strip()

        if values:

            records.append(
                values
            )

    def key_fn(
        item: dict[str, str]
    ):

        exam_id = item.get(
            "course_exam_id",
            "",
        )

        if exam_id.isdigit():

            return (
                0,
                int(exam_id),
            )

        return (
            1,
            exam_id,
        )

    records.sort(
        key=key_fn
    )

    return records


# ============================================================
# DETERMINISTIC ANSWERS
# ============================================================

def deterministic_answer(
    query: str,
    results: list[dict[str, Any]],
) -> str | None:

    q = (
        query or ""
    ).lower()

    # --------------------------------------------------------
    # STUDENT EXAMS
    # --------------------------------------------------------

    student_records = (
        extract_student_records(
            results
        )
    )

    if student_records:

        if (
            "student ids" in q
            or "student id" in q
        ):

            ids = sorted(
                {
                    r.get(
                        "student_id"
                    )
                    for r in student_records
                    if r.get(
                        "student_id"
                    )
                }
            )

            return (
                "Answer:\n"
                + "\n".join(
                    str(student_id)
                    for student_id in ids
                )
            )

        if (
            "student" in q
            and "exam" in q
        ):

            lines = []

            for record in student_records:

                lines.append(
                    (
                        f"Student "
                        f"{record.get('student_id')} "
                        f"-> Course "
                        f"{record.get('course_id')} "
                        f"-> "
                        f"{record.get('exam_name')} "
                        f"-> "
                        f"{record.get('exam_date')} "
                        f"{record.get('exam_time')} "
                        f"-> Status: "
                        f"{record.get('status')}"
                    )
                )

            return (
                "Answer:\n"
                + "\n".join(lines)
            )

        if (
            "how many students"
            in q
            or "student count"
            in q
        ):

            unique_students = {
                r.get(
                    "student_id"
                )
                for r in student_records
                if r.get(
                    "student_id"
                )
            }

            return (
                "Answer:\n"
                f"There are "
                f"{len(unique_students)} "
                "unique students in "
                "the retrieved evidence."
            )

    # --------------------------------------------------------
    # COURSE EXAMS
    # --------------------------------------------------------

    course_exam_records = (
        extract_course_exam_records(
            results
        )
    )

    if course_exam_records:

        if (
            "course exam" in q
            or "exam date" in q
            or "exam schedule" in q
            or "when is" in q
        ):

            lines = []

            for exam in course_exam_records:

                lines.append(
                    (
                        f"Course "
                        f"{exam.get('course_id')} "
                        f"-> "
                        f"{exam.get('exam_name')} "
                        f"-> "
                        f"{exam.get('exam_date')} "
                        f"{exam.get('exam_time')}"
                    )
                )

            return (
                "Answer:\n"
                + "\n".join(lines)
            )

        if (
            "how many exams" in q
            or "exam count" in q
        ):

            return (
                "Answer:\n"
                f"There are "
                f"{len(course_exam_records)} "
                "course exams in "
                "the retrieved evidence."
            )

    return None


# ============================================================
# OLLAMA
# ============================================================

def generate_with_ollama(
    query: str,
    context: str,
) -> str:

    messages = [
        {
            "role": "system",
            "content": (
                "You are a retrieval-grounded assistant. "
                "Answer using only the provided context. "
                "Do not invent information. "
                "If the context does not contain enough "
                "evidence to answer the question, say "
                "'Insufficient evidence.'"
            ),
        },
        {
            "role": "user",
            "content": (
                f"QUESTION:\n"
                f"{query}\n\n"
                f"CONTEXT:\n"
                f"{context}\n\n"
                "Answer the question using only the context."
            ),
        },
    ]

    try:
        return create_chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0,
        )

    except Exception as exc:
        return f"LLM unavailable: {exc}"


# ============================================================
# ANSWER QUESTION
# ============================================================

def answer_question(
    query: str,
    k: int = 5,
    caller: str = "student",
) -> dict[str, Any]:

    start = time.time()

    retrieval = retrieve_context(
        query=query,
        k=k,
        caller=caller,
    )

    if (
        retrieval.get(
            "status"
        )
        != "success"
    ):

        output = {
            "status": "error",
            "query": query,
            "error": retrieval.get(
                "error",
                "retrieval_failed",
            ),
        }

        append_audit(
            "answer_question",
            {
                "query": query,
                "k": k,
                "caller": caller,
            },
            output,
            "fail",
            "retrieval_failed",
            start,
        )

        return output

    results = retrieval.get(
        "results",
        [],
    )

    context = "\n\n".join(
        r.get(
            "text",
            "",
        )
        for r in results
    )

    answer = deterministic_answer(
        query,
        results,
    )

    if answer is None:

        answer = generate_with_ollama(
            query,
            context,
        )

    citations = [
        {
            "chunk_id": r.get(
                "chunk_id"
            ),
            "source_id": r.get(
                "source_id"
            ),
            "authority_tier": r.get(
                "authority_tier"
            ),
        }
        for r in results
    ]

    confidence = (
        confidence_from_results(
            results
        )
    )

    output = {
        "status": "success",
        "query": query,
        "answer": answer,
        "citations": citations,
        "confidence_category": confidence,
        "retrieval_summary": {
            "k": k,
            "retrieved_count": len(
                results
            ),
            "top_chunk": (
                results[0].get(
                    "chunk_id"
                )
                if results
                else None
            ),
        },
    }

    append_audit(
        "answer_question",
        {
            "query": query,
            "k": k,
            "caller": caller,
        },
        {
            "confidence_category": confidence,
            "citation_count": len(
                citations
            ),
        },
        "pass",
        "answer_generated",
        start,
    )

    return output


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        json.dumps(
            refresh_corpus(),
            indent=2,
        )
    )

    print(
        json.dumps(
            retrieve_context(
                "course exams",
                5,
            ),
            indent=2,
        )
    )

    print(
        json.dumps(
            answer_question(
                "What exams are available?",
                5,
            ),
            indent=2,
        )
    )

    print(
        json.dumps(
            answer_question(
                "Which students have exams?",
                5,
            ),
            indent=2,
        )
    )
