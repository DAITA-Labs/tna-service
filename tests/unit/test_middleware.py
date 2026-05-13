"""Tests for app/core/middleware — RequestIdMiddleware."""
from fastapi.testclient import TestClient
from app.main import app


def test_request_id_attached_in_response_header():
    client = TestClient(app)
    r = client.get("/health")
    assert "x-request-id" in {k.lower() for k in r.headers}


def test_request_id_from_caller_is_echoed():
    client = TestClient(app)
    r = client.get("/health", headers={"x-request-id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
