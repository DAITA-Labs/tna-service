"""Shared fixtures for the test suite."""
from pathlib import Path
import pytest


# Datasets live one level up from tna-service/.
DATASET_DIR = Path(__file__).resolve().parents[2] / "dataset"


@pytest.fixture
def dkn_file():
    p = DATASET_DIR / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def compass_pro_manos_file():
    p = DATASET_DIR / "20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def northern_reflections_file():
    p = DATASET_DIR / "NORTHERN REFLECTIONS- T&a.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def orders_plan_file():
    p = DATASET_DIR / "63261-TNA.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def christian_berg_file():
    p = DATASET_DIR / "CHRISTIAN BERG- T&A.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture(autouse=True)
def _clear_workbook_cache():
    from app.repositories.workbook_repo import clear_cache
    clear_cache()
    yield
    clear_cache()
