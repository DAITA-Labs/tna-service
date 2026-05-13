"""Label directory resolver — resolves to the local dataset/extracted/ shipped
with the microservice. Self-contained: no path outside tna-service/."""
from pathlib import Path

# Local copy of the labeled corpus under tna-service/dataset/extracted/.
# evals/_label_dir.py → evals → tna-service → dataset / extracted
LABELS_DIR = (Path(__file__).resolve().parents[1] / "dataset" / "extracted").resolve()
