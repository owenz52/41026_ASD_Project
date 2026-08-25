import requests


# ---------------------------------------------------------------------------
# CRUD (normal_ui.py) — services.database_api is mocked at the module level,
# since routes/normal_ui.py does `from services import database_api` and looks
# up functions on that module object at call time.
# ---------------------------------------------------------------------------

def test_list_notebooks_success(client, mocker):
    mocker.patch(
        "services.database_api.list_notebooks",
        return_value=(200, [{"notebook_id": 1, "student_id": 1001, "course_id": 1,
                              "notebook_title": "Test", "created_date": "2026-08-01"}]),
    )
    response = client.get("/notebooks?student_id=1001")
    assert response.status_code == 200
    assert response.get_json()[0]["notebook_id"] == 1


def test_get_notebook_not_found(client, mocker):
    mocker.patch(
        "services.database_api.get_notebook",
        return_value=(404, {"error": "notebook not found"}),
    )
    response = client.get("/notebooks/999")
    assert response.status_code == 404
    assert response.get_json()["error"] == "notebook not found"


def test_create_notebook_success(client, mocker):
    mocker.patch(
        "services.database_api.create_notebook",
        return_value=(201, {"notebook_id": 11, "student_id": 1001, "course_id": 1,
                             "notebook_title": "New Notebook", "created_date": "2026-08-25"}),
    )
    response = client.post("/notebooks", json={
        "student_id": 1001, "course_id": 1, "notebook_title": "New Notebook"
    })
    assert response.status_code == 201
    assert response.get_json()["notebook_id"] == 11


def test_update_notebook_partial(client, mocker):
    mocker.patch(
        "services.database_api.update_notebook",
        return_value=(200, {"notebook_id": 1, "student_id": 1001, "course_id": 1,
                             "notebook_title": "Renamed", "created_date": "2026-08-01"}),
    )
    response = client.put("/notebooks/1", json={"notebook_title": "Renamed"})
    assert response.status_code == 200
    assert response.get_json()["notebook_title"] == "Renamed"


def test_delete_notebook_success(client, mocker):
    mocker.patch(
        "services.database_api.delete_notebook",
        return_value=(200, {"deleted": True, "notebook_id": 1}),
    )
    response = client.delete("/notebooks/1")
    assert response.status_code == 200
    assert response.get_json()["deleted"] is True


def test_list_notes_for_notebook(client, mocker):
    mocker.patch(
        "services.database_api.list_notes",
        return_value=(200, [{"note_id": 1, "notebook_id": 1, "note_title": "N",
                              "note_content": "C", "updated_date": "2026-08-01"}]),
    )
    response = client.get("/notebooks/1/notes")
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def test_create_note_success(client, mocker):
    mocker.patch(
        "services.database_api.create_note",
        return_value=(201, {"note_id": 25, "notebook_id": 1, "note_title": "N",
                             "note_content": "C", "updated_date": "2026-08-25"}),
    )
    response = client.post("/notes", json={
        "notebook_id": 1, "note_title": "N", "note_content": "C"
    })
    assert response.status_code == 201


def test_update_note_success(client, mocker):
    mocker.patch(
        "services.database_api.update_note",
        return_value=(200, {"note_id": 1, "notebook_id": 1, "note_title": "Updated",
                             "note_content": "C", "updated_date": "2026-08-25"}),
    )
    response = client.put("/notes/1", json={"note_title": "Updated"})
    assert response.status_code == 200


def test_delete_note_success(client, mocker):
    mocker.patch(
        "services.database_api.delete_note",
        return_value=(200, {"deleted": True, "note_id": 1}),
    )
    response = client.delete("/notes/1")
    assert response.status_code == 200


def test_search_notes_missing_q_returns_400(client, mocker):
    mocker.patch(
        "services.database_api.search_notes",
        return_value=(400, {"error": "q is required"}),
    )
    response = client.get("/notes/search")
    assert response.status_code == 400
    assert response.get_json()["error"] == "q is required"


def test_search_notes_with_query_and_course_id(client, mocker):
    mocker.patch(
        "services.database_api.search_notes",
        return_value=(200, [{"note_id": 1, "notebook_id": 1, "note_title": "Docker Intro",
                              "note_content": "...", "updated_date": "2026-08-01",
                              "course_id": 1}]),
    )
    response = client.get("/notes/search?q=docker&course_id=1")
    assert response.status_code == 200
    assert response.get_json()[0]["course_id"] == 1


# ---------------------------------------------------------------------------
# AI summarise (routes/ai_mode.py) — services.ai_orchestrator imports get_note,
# ask_llm, search_notes directly by name, so mocks target the bound names on
# services.ai_orchestrator itself, not their original definitions.
# ---------------------------------------------------------------------------

SHORT_NOTE = {"note_id": 1, "notebook_id": 1, "note_title": "Short",
              "note_content": "Too short to summarise."}

MEDIUM_NOTE = {"note_id": 2, "notebook_id": 1, "note_title": "Medium Note",
               "note_content": "word " * 100}


def test_missing_note_id_returns_400_for_summarise(client):
    response = client.post("/ai/summarise", json={})
    assert response.status_code == 400


def test_missing_note_id_returns_400_for_recommend(client):
    response = client.post("/ai/recommend", json={})
    assert response.status_code == 400


def test_summarise_note_not_found_returns_404(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(404, {"error": "note not found"}))
    response = client.post("/ai/summarise", json={"note_id": 999})
    assert response.status_code == 404


def test_summarise_short_note_skips_llm(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SHORT_NOTE))
    ask_llm_mock = mocker.patch("services.ai_orchestrator.ask_llm")

    response = client.post("/ai/summarise", json={"note_id": 1})

    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"] == SHORT_NOTE["note_content"]
    assert body["trace"]["plan"]["strategy"] == "skip_llm"
    ask_llm_mock.assert_not_called()


def test_summarise_direct_pass(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, MEDIUM_NOTE))
    mocker.patch("services.ai_orchestrator.ask_llm", return_value="A short summary.")

    response = client.post("/ai/summarise", json={"note_id": 2})

    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"] == "A short summary."
    assert body["trace"]["plan"]["strategy"] == "direct_single_pass"
    assert body["trace"]["adapt"]["action"] == "none"


def test_summarise_adapt_retry_on_empty_output(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, MEDIUM_NOTE))
    mocker.patch("services.ai_orchestrator.ask_llm", side_effect=["", "Retried summary."])

    response = client.post("/ai/summarise", json={"note_id": 2})

    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"] == "Retried summary."
    assert body["trace"]["adapt"]["action"] == "retried_with_stricter_prompt"
    assert body["trace"]["adapt"]["retry_count"] == 1


def test_summarise_adapt_truncate_when_not_shorter(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, MEDIUM_NOTE))
    not_shorter_output = "x" * (len(MEDIUM_NOTE["note_content"]) + 50)
    mocker.patch("services.ai_orchestrator.ask_llm", return_value=not_shorter_output)

    response = client.post("/ai/summarise", json={"note_id": 2})

    assert response.status_code == 200
    body = response.get_json()
    assert body["trace"]["adapt"]["action"] == "truncated"
    assert len(body["summary"]) < len(MEDIUM_NOTE["note_content"])


def test_summarise_ollama_unreachable_returns_502(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, MEDIUM_NOTE))
    mocker.patch(
        "services.ai_orchestrator.ask_llm",
        side_effect=requests.exceptions.ConnectionError("connection refused"),
    )

    response = client.post("/ai/summarise", json={"note_id": 2})

    assert response.status_code == 502
    assert response.get_json()["error"] == "AI service unavailable"


def test_summarise_skip_threshold_is_env_overridable(client, mocker, monkeypatch):
    # Proves ai_orchestrator reads thresholds fresh per call (config.get_cfg),
    # not as a module-level constant cached at import time.
    monkeypatch.setenv("SUMMARY_SKIP_THRESHOLD_CHARS", "0")
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SHORT_NOTE))
    ask_llm_mock = mocker.patch("services.ai_orchestrator.ask_llm", return_value="summary")

    response = client.post("/ai/summarise", json={"note_id": 1})

    assert response.status_code == 200
    assert response.get_json()["trace"]["plan"]["strategy"] != "skip_llm"
    ask_llm_mock.assert_called_once()


# ---------------------------------------------------------------------------
# AI recommend
# ---------------------------------------------------------------------------

SOURCE_NOTE = {"note_id": 3, "notebook_id": 1, "note_title": "Flask REST API Design Patterns",
               "note_content": "Flask routes should stay thin. " * 10}

CANDIDATES = [
    {"note_id": 1, "notebook_id": 1, "note_title": "Intro to Microservices with Docker",
     "note_content": "Docker packages an application.", "updated_date": "2026-07-29", "course_id": 1},
    {"note_id": 4, "notebook_id": 2, "note_title": "SQL Joins and Normalization",
     "note_content": "Normalization structures a database.", "updated_date": "2026-07-31", "course_id": 3},
]


def test_recommend_note_not_found_returns_404(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(404, {"error": "note not found"}))
    response = client.post("/ai/recommend", json={"note_id": 999})
    assert response.status_code == 404


def test_recommend_returns_llm_ranked_candidates(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SOURCE_NOTE))
    mocker.patch("services.ai_orchestrator.search_notes", return_value=(200, CANDIDATES))
    mocker.patch(
        "services.ai_orchestrator.ask_llm",
        return_value="Intro to Microservices with Docker\nSQL Joins and Normalization",
    )

    response = client.post("/ai/recommend", json={"note_id": 3})

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["recommendations"]) == 2
    assert body["trace"]["adapt"]["action"] == "none"
    assert body["trace"]["observe"]["hallucination_detected"] is False


def test_recommend_hallucination_triggers_fallback(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SOURCE_NOTE))
    mocker.patch("services.ai_orchestrator.search_notes", return_value=(200, CANDIDATES))
    mocker.patch(
        "services.ai_orchestrator.ask_llm",
        return_value="A Note That Does Not Exist In The Candidate Set",
    )

    response = client.post("/ai/recommend", json={"note_id": 3})

    assert response.status_code == 200
    body = response.get_json()
    assert body["trace"]["observe"]["hallucination_detected"] is True
    assert body["trace"]["adapt"]["action"] == "fallback_keyword_overlap"


def test_recommend_caps_at_max_recommendations(client, mocker):
    many_candidates = [
        {"note_id": i, "notebook_id": 1, "note_title": f"Note {i}",
         "note_content": "Flask routes should stay thin.", "updated_date": "2026-08-01",
         "course_id": 1}
        for i in range(4, 10)
    ]
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SOURCE_NOTE))
    mocker.patch("services.ai_orchestrator.search_notes", return_value=(200, many_candidates))
    mocker.patch(
        "services.ai_orchestrator.ask_llm",
        return_value="\n".join(c["note_title"] for c in many_candidates),
    )

    response = client.post("/ai/recommend", json={"note_id": 3})

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["recommendations"]) <= 3


def test_recommend_no_candidates_returns_empty_list(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SOURCE_NOTE))
    mocker.patch("services.ai_orchestrator.search_notes", return_value=(200, []))
    ask_llm_mock = mocker.patch("services.ai_orchestrator.ask_llm")

    response = client.post("/ai/recommend", json={"note_id": 3})

    assert response.status_code == 200
    assert response.get_json()["recommendations"] == []
    ask_llm_mock.assert_not_called()


def test_recommend_ollama_unreachable_returns_502(client, mocker):
    mocker.patch("services.ai_orchestrator.get_note", return_value=(200, SOURCE_NOTE))
    mocker.patch("services.ai_orchestrator.search_notes", return_value=(200, CANDIDATES))
    mocker.patch(
        "services.ai_orchestrator.ask_llm",
        side_effect=requests.exceptions.ConnectionError("connection refused"),
    )

    response = client.post("/ai/recommend", json={"note_id": 3})

    assert response.status_code == 502
    assert response.get_json()["error"] == "AI service unavailable"
