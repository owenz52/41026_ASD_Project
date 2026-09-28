# Shared MCP and RAG services

These services run on the host machine, outside Docker Compose. Feature backends
run in Docker and supply student-scoped data to the shared services.

## Local addresses

| Service | Host process | Address from a Docker container |
|---|---|---|
| MCP | `python ai-services/mcp-server/server.py` | `http://host.docker.internal:8011/mcp` |
| RAG | `python ai-services/rag-server/server.py` | `http://host.docker.internal:8012` |
| Agentic loop | `python ai-services/agentic-loop/app.py` | `http://host.docker.internal:5012` |

The host can use `127.0.0.1` instead of `host.docker.internal`.

## MCP tools

Add feature tools to `ai-services/mcp-server/server.py` using `@mcp.tool()`.
Give each tool a feature-prefixed name, typed inputs, a short description,
and a structured return type. For example, the existing tool is
`assessments_get_upcoming(student_id, days_ahead=14)`.

Feature code should call tools through an MCP client. The `/mcp` address is an
MCP transport endpoint, not an ordinary JSON REST endpoint.

The feature backend is responsible for determining the current student and
passing that student's ID. A tool must fetch or return only records that the
student is permitted to access.

## RAG request

Feature backends send `POST /answer` with JSON:

```json
{
  "query": "When is my Architecture Report due?",
  "feature": "assessments",
  "student_id": 1,
  "k": 5,
  "documents": [
    {
      "feature": "assessments",
      "student_id": 1,
      "chunk_id": "assessment:11",
      "source_id": "assessment:11",
      "authority_tier": "tier_1",
      "text": "The Architecture Report is due on 2026-10-05."
    }
  ]
}
```

`k` is optional and defaults to 5. Each `chunk_id` must be unique within the
request. Use a stable `source_id` that the frontend can show to the student.
The backend prepares fresh documents from its own records for each request.
The RAG server does not maintain a persistent student corpus.

The backend must fetch only the current student's records. The RAG server
checks that supplied document `feature` and `student_id` values match the
request, but it does not authenticate users.

## RAG response

A grounded answer has this shape:

```json
{
  "status": "success",
  "query": "When is my Architecture Report due?",
  "answer": "[assessment:11]: 2026-10-05",
  "citations": ["assessment:11"],
  "confidence": "Context Available",
  "sources": [
    {
      "chunk_id": "assessment:11",
      "source_id": "assessment:11",
      "authority_tier": "tier_1",
      "text": "The Architecture Report is due on 2026-10-05."
    }
  ]
}
```

If relevant context is unavailable, `status` is `insufficient_context`,
`citations` and `sources` are empty, and `confidence` is
`Insufficient Context`. `Context Available` means cited context was retrieved;
it is not a probability or a guarantee that the generated answer is correct.

`POST /retrieve` accepts the same request and returns ranked context without
calling Ollama. `GET /health` checks whether the RAG HTTP server is running.

## Shared loop validation

`POST http://localhost:5012/validate-now` checks MCP tool discovery and RAG
retrieval using a synthetic document. The normal loop also runs these checks
during polling. This check does not execute feature tools or assess the
accuracy of generated answers.

Discuss changes to these shared schemas with the group before teammates build
against them.