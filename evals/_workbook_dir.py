"""Workbook directory resolver — resolves to the local dataset/ shipped with
the microservice. Self-contained: no path outside tna-service/."""
from pathlib import Path

# Local copy of the workbook corpus under tna-service/dataset/.
WORKBOOKS_DIR = (Path(__file__).resolve().parents[1] / "dataset").resolve()
