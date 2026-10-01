import os
import requests


RAG_SERVICE_URL = os.getenv(
    "RAG_SERVICE_URL",
    "http://host.docker.internal:8012"
)


try:
    RAG_SERVICE_TIMEOUT_SECONDS = int(
        os.getenv(
            "RAG_SERVICE_TIMEOUT_SECONDS",
            "180"
        )
    )
except ValueError:
    RAG_SERVICE_TIMEOUT_SECONDS = 180


# ==================================================
# CALL RAG SERVICE
# ==================================================

def call_rag_service(
    path: str,
    payload: dict
):
    response = requests.post(
        f"{RAG_SERVICE_URL}{path}",
        json=payload,
        timeout=RAG_SERVICE_TIMEOUT_SECONDS,
    )

    try:
        data = response.json()

    except ValueError as exc:
        response.raise_for_status()

        raise requests.RequestException(
            "RAG service returned a non-JSON response"
        ) from exc

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"RAG service {path} failed "
            f"with status {response.status_code}: {data}",
            response=response,
        )

    return data
