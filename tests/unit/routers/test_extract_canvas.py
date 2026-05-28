"""POST /extract_canvas endpoint — contract tests with a mocked service."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.extraction import ExtractionResult, Warning


client = TestClient(app)


def test_rejects_non_xlsx_upload() -> None:
    """An upload without .xlsx suffix → 400."""
    resp = client.post(
        "/extract_canvas",
        files={"file": ("data.csv", BytesIO(b"col1,col2"), "text/csv")},
    )
    assert resp.status_code == 400
    assert "xlsx" in resp.json()["detail"].lower()


def test_endpoint_returns_extraction_result_shape() -> None:
    """A successful service call passes through to the ExtractResponse contract."""
    fake_result = ExtractionResult(
        plis=[],
        warnings=[Warning(message="no clusters", severity="warning")],
        source_file="test.xlsx",
    )
    with patch("app.routers.extract_canvas.extract_canvas", return_value=fake_result):
        resp = client.post(
            "/extract_canvas",
            files={"file": ("test.xlsx", BytesIO(b"fake bytes"),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plis"] == []
    assert len(body["warnings"]) == 1
    assert body["warnings"][0]["message"] == "no clusters"


def test_endpoint_500_on_service_failure() -> None:
    with patch("app.routers.extract_canvas.extract_canvas",
                 side_effect=RuntimeError("boom")):
        resp = client.post(
            "/extract_canvas",
            files={"file": ("test.xlsx", BytesIO(b"fake"),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 500
    assert "boom" in resp.json()["detail"]
