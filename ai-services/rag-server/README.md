# Shared RAG Server

Answers questions about the project's own data, grounded in retrieved context
and returned with the sources the answer came from and a confidence level.

## Running it

Under Docker Compose it starts with everything else:

```bash
docker compose up --build
```

Standalone:

```bash
pip install -r requirements.txt
python app.py
```

It listens on port 5200.

## What it indexes

The knowledge base is built at startup from the feature database services, so
answers come from the student's real records rather than fixed text:

| Source | Indexed as |
|---|---|
| Exam service | One passage per exam, with its date and time |
| Assessment Tracker | One passage per assignment, with due date, weighting and status |
| Calendar | One passage per event, with its start time and location |
| Course catalogue | One passage per course |
| Enrolments | One passage per enrolment record |
| Notebook | One passage per note |
| `documents/` | One passage per paragraph of any `.md` or `.txt` file |

Records from the student's own data are ranked above general documentation, so
"when is my exam" returns the exam entry rather than a page describing what the
exam feature does.

Add your own material by dropping Markdown files into `documents/`, then
`POST /reindex`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, passage count and what was indexed |
| GET | `/documents` | What the index was built from |
| POST | `/query` | `{"question": str, "top_k": int}` |
| POST | `/reindex` | Rebuild the index from the feature services |

## How answers stay grounded

Retrieval runs first. If no passage clears the relevance floor, **the model is
never called** and an insufficient-context response is returned. An answer not
supported by retrieved material is worse than no answer, because a student
cannot tell the difference between a fact from their records and something
invented.

Three further guards:

- The prompt forbids using anything outside the supplied passages, and
  instructs the model to reply `INSUFFICIENT_CONTEXT` if they do not answer the
  question. That reply is honoured rather than shown.
- Every answer carries citations naming the record it came from.
- Confidence is derived from retrieval quality, not claimed by the model.

If Ollama is unavailable the server still answers, returning the retrieved
passages themselves with `generated: false`. The answer stays grounded; only
the phrasing is lost.

## Retrieval

BM25 over the indexed passages, implemented in plain Python. No embedding model
is downloaded, so the container starts quickly and works without network
access. For a corpus of this size lexical ranking is accurate enough and fully
deterministic, which also makes it testable.

## Configuration

| Variable | Default |
|---|---|
| `RAG_PORT` | 5200 |
| `RAG_TOP_K` | 4 |
| `RAG_RECORD_WEIGHT` | 1.6 |
| `RAG_DOCUMENTS_DIR` | documents |
| `OLLAMA_BASE_URL` | http://host.docker.internal:11434 |
| `OLLAMA_MODEL` | qwen2.5:0.5b |
| `ENROLMENT_DB_URL` … `EXAM_DB_URL` | the feature database services |

## Tests

```bash
python test_rag_server.py
```

32 checks, using stub feature services and a stub model. Covers grounded
answers, retrieval accuracy, insufficient context, the model's own refusal,
Ollama being unavailable, and a feature service being down during indexing.
