"""Tests for app/routers + app/main."""
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.models.extraction import ExtractionResult, PLI


def test_health_returns_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_metrics_endpoint_serves_prometheus():
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    # Default Prometheus exposition format — at least one of our collectors
    # must appear (extraction_duration_seconds is registered at import time
    # via app.core.telemetry).
    assert "extraction_duration_seconds" in r.text


def test_extract_endpoint_calls_orchestrator(tmp_path):
    from openpyxl import Workbook
    wb = Workbook(); wb.active["A1"] = "hello"
    p = tmp_path / "sample.xlsx"; wb.save(p)
    fake_result = ExtractionResult(
        plis=[PLI(io_number="ABC")], source_file=str(p),
        format_detected="tabular_columnar",
    )
    with patch("app.routers.extract.extract", return_value=fake_result):
        client = TestClient(app)
        with open(p, "rb") as fh:
            r = client.post("/extract", files={"file": ("sample.xlsx", fh)})
    assert r.status_code == 200
    body = r.json()
    assert len(body["plis"]) == 1
    assert body["plis"][0]["io_number"] == "ABC"
