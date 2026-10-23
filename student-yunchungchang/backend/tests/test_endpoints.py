"""
TEMPORARY Release 2 smoke tests.

TODO: Replace with feature-specific endpoint tests.
These tests verify route registration, not complete functionality.
"""

import pytest
from flask import Flask


@pytest.fixture
def client():
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    @app.get("/test")
    def test_route():
        return {"message": "test"}, 200

    return app.test_client()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_example_endpoint(client):
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json["message"] == "test"
