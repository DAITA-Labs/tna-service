"""Smoke test for scripts/run_eval.py — imports + adapter satisfies Protocol.

Does NOT run the full eval (which requires a real ANTHROPIC_API_KEY).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals.interface import ExtractorProtocol


def test_adapter_satisfies_extractor_protocol():
    import importlib.util
    spec_path = ROOT / "scripts" / "run_eval.py"
    spec = importlib.util.spec_from_file_location("run_eval", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    adapter = mod.TnaServiceExtractor()
    assert isinstance(adapter, ExtractorProtocol)
