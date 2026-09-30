import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from rag_answer import answer_with_context
from rag_pipeline import retrieve_context


class RAGHandler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"service": "shared-rag", "status": "ok"})
        else:
            self.send_json(404, {"status": "error", "message": "Not found"})

    def do_POST(self) -> None:
        if self.path not in ("/retrieve", "/answer"):
            self.send_json(404, {"status": "error", "message": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 500_000:
                raise ValueError("Request body must be between 1 and 500000 bytes")

            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")

            retrieval = retrieve_context(
                query=payload["query"],
                feature=payload["feature"],
                student_id=payload["student_id"],
                documents=payload["documents"],
                k=payload.get("k", 5),
            )

            if self.path == "/retrieve":
                self.send_json(200, retrieval)
                return

            answer = answer_with_context(payload["query"], retrieval)
            self.send_json(200, {
                **answer,
                "query": payload["query"],
                "sources": [
                    {
                        "chunk_id": item["chunk_id"],
                        "source_id": item["source_id"],
                        "authority_tier": item["authority_tier"],
                        "text": item["text"],
                    }
                    for item in retrieval["results"]
                    if item["source_id"] in answer["citations"]
                ],
            })

        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.send_json(400, {"status": "error", "message": str(exc)})
        except requests.RequestException:
            self.send_json(502, {
                "status": "error",
                "message": "The local Ollama service is unavailable",
            })


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8012), RAGHandler)
    print("Shared RAG server listening on port 8012", flush=True)
    server.serve_forever()