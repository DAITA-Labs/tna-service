"""MetadataGate — routes novel-canonical MetadataEntry items to the judge."""
from __future__ import annotations

from haystack import Pipeline

from app.components.judges.metadata_gate import (
    MetadataGate,
    _apply_verdict,
    _parse_cell_ref,
    _render_metadata_catalog,
)
from app.agents.judges.metadata.schema import MetadataVerdict
from app.specs.schemas import MetadataEntry
from tests.fixtures.fake_llm import FakeLLM
from tests.unit.components.field._bundles import make_bundle


def _bundle():
    return make_bundle([[None] * 5 for _ in range(8)], "io_number", columns={}, rows={})


def _entry(**overrides) -> MetadataEntry:
    base = dict(key="Treatment", value="Garment Dye", source="K4", canonical=None)
    base.update(overrides)
    return MetadataEntry(**base)


def _verdict(decision: str, alt: str | None = None) -> dict:
    return {"decision": decision, "alternative_canonical": alt,
            "reason": "test reason", "confidence": "medium"}


# ─── Short-circuit paths ─────────────────────────────────────────────────


def test_no_entries_returns_empty() -> None:
    gate = MetadataGate(llm=FakeLLM(canned={}))
    out = gate.run(metadata_entries=[], bundle=_bundle())
    assert out["metadata_entries"] == []


def test_entry_with_canonical_set_passes_through() -> None:
    gate = MetadataGate(llm=FakeLLM(canned={}))
    entries = [_entry(canonical="buyer")]
    out = gate.run(metadata_entries=entries, bundle=_bundle())
    assert out["metadata_entries"] == entries


# ─── Verdict application ─────────────────────────────────────────────────


def test_keep_verdict_preserves_entry() -> None:
    llm = FakeLLM(canned={"MetadataVerdict": _verdict("keep")})
    gate = MetadataGate(llm=llm)
    out = gate.run(metadata_entries=[_entry()], bundle=_bundle())
    assert len(out["metadata_entries"]) == 1
    assert out["metadata_entries"][0].canonical is None


def test_drop_verdict_removes_entry() -> None:
    llm = FakeLLM(canned={"MetadataVerdict": _verdict("drop")})
    gate = MetadataGate(llm=llm)
    out = gate.run(metadata_entries=[_entry()], bundle=_bundle())
    assert out["metadata_entries"] == []


def test_rewrite_verdict_sets_canonical() -> None:
    llm = FakeLLM(canned={"MetadataVerdict": _verdict("rewrite", alt="buyer")})
    gate = MetadataGate(llm=llm)
    out = gate.run(metadata_entries=[_entry(key="Buyer Name", value="Nike")], bundle=_bundle())
    adjudicated = out["metadata_entries"][0]
    assert adjudicated.canonical == "buyer"


def test_agent_failure_keeps_entry() -> None:
    bad = {"decision": "rewrite", "alternative_canonical": "made_up",
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = MetadataGate(llm=llm)
    original = _entry()
    out = gate.run(metadata_entries=[original], bundle=_bundle())
    assert out["metadata_entries"] == [original]


def test_mix_of_canonical_and_novel_routes_only_novel() -> None:
    llm = FakeLLM(canned={"MetadataVerdict": _verdict("keep")})
    gate = MetadataGate(llm=llm)
    entries = [_entry(key="Buyer", canonical="buyer"),       # already resolved
               _entry(key="Treatment", canonical=None)]      # novel → judge fires
    out = gate.run(metadata_entries=entries, bundle=_bundle())
    assert len(out["metadata_entries"]) == 2
    assert out["metadata_entries"][0].canonical == "buyer"
    assert out["metadata_entries"][1].canonical is None


# ─── Helpers ─────────────────────────────────────────────────────────────


def test_apply_verdict_keep_returns_same() -> None:
    e = _entry()
    v = MetadataVerdict(decision="keep", reason="x", confidence="medium")
    assert _apply_verdict(e, v) is e


def test_apply_verdict_drop_returns_none() -> None:
    v = MetadataVerdict(decision="drop", reason="x", confidence="low")
    assert _apply_verdict(_entry(), v) is None


def test_apply_verdict_rewrite_sets_canonical() -> None:
    v = MetadataVerdict(decision="rewrite", alternative_canonical="season",
                          reason="x", confidence="high")
    new = _apply_verdict(_entry(), v)
    assert new is not None
    assert new.canonical == "season"


def test_render_metadata_catalog_lists_known_canonicals() -> None:
    text = _render_metadata_catalog()
    assert "buyer" in text
    assert "aliases:" in text


def test_parse_cell_ref_typical() -> None:
    assert _parse_cell_ref("K4") == ("K", 4)
    assert _parse_cell_ref("aa12") == ("AA", 12)


def test_parse_cell_ref_invalid_returns_none() -> None:
    assert _parse_cell_ref("") is None
    assert _parse_cell_ref("4K") is None
    assert _parse_cell_ref("K") is None


# ─── Component plumbing ─────────────────────────────────────────────────


def test_gate_sockets_registered() -> None:
    gate = MetadataGate(llm=FakeLLM(canned={}))
    assert "metadata_entries" in gate.__haystack_input__._sockets_dict
    assert "bundle" in gate.__haystack_input__._sockets_dict
    assert "metadata_entries" in gate.__haystack_output__._sockets_dict


def test_gate_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("metadata_judge", MetadataGate(llm=FakeLLM(canned={})))
    assert "metadata_judge" in pipeline.graph.nodes
