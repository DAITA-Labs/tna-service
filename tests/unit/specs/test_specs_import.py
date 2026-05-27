"""Smoke tests proving app.specs is importable and registries are populated.

Run with: pytest tests/unit/specs/test_specs_import.py -v
"""
from __future__ import annotations


def test_identifier_specs_loaded() -> None:
    """All 11 identifier canonicals must be present in IDENTIFIER_SPECS."""
    from app.specs.identifiers import IDENTIFIER_SPECS

    canonicals = {s.canonical for s in IDENTIFIER_SPECS}
    expected = {
        "io_number", "style_code", "style_name",
        "color_code", "color_name",
        "fabric_code", "fabric_name",
        "quantity",
        "delivery_date", "shipment_date", "ex_fty_date",
    }
    assert canonicals == expected


def test_stage_specs_include_canvas_additions() -> None:
    """Stage registry must include VAP, line_plan, feeding (added during canvas eval)."""
    from app.specs.stages import STAGE_SPECS

    canonicals = {s.canonical for s in STAGE_SPECS}
    assert "fabric" in canonicals
    assert "vap" in canonicals
    assert "line_plan" in canonicals
    assert "feeding" in canonicals
    assert "sewing" in canonicals


def test_subfield_specs_include_status() -> None:
    """Subfield registry must include status (added during canvas eval)."""
    from app.specs.subfields import SUBFIELD_SPECS

    canonicals = {s.canonical for s in SUBFIELD_SPECS}
    assert "status" in canonicals
    assert "planned_date" in canonicals
    assert "actual_date" in canonicals
    assert "remarks" in canonicals


def test_metadata_specs_loaded() -> None:
    """Metadata registry must be populated with at least buyer/season/factory."""
    from app.specs.metadata import METADATA_SPECS

    canonicals = {s.canonical for s in METADATA_SPECS}
    assert "buyer" in canonicals
    assert "season" in canonicals
    assert "factory" in canonicals


def test_package_init_reexports() -> None:
    """The package-level re-exports must work for the headline names."""
    from app.specs import (
        IDENTIFIER_SPECS,
        STAGE_SPECS,
        SUBFIELD_SPECS,
        METADATA_SPECS,
        FieldSpec,
        StageSpec,
        SubfieldSpec,
        ValueConstraints,
        Area,
        LabelMatchMode,
        ValueDtype,
    )

    assert len(IDENTIFIER_SPECS) == 11
    assert all(isinstance(s, FieldSpec) for s in IDENTIFIER_SPECS)
    assert all(isinstance(s, StageSpec) for s in STAGE_SPECS)
    assert all(isinstance(s, SubfieldSpec) for s in SUBFIELD_SPECS)


def test_legacy_experiments_specs_compat() -> None:
    """experiments/specs/__init__.py keeps re-exporting for canvas-probe back-compat."""
    from experiments.specs import IO_NUMBER_SPEC, STAGE_SPECS, render_field_finding_judge_prompt

    assert IO_NUMBER_SPEC.canonical == "io_number"
    assert any(s.canonical == "fabric" for s in STAGE_SPECS)
    assert callable(render_field_finding_judge_prompt)


def test_quantity_anti_patterns_present() -> None:
    """Quantity spec's anti-patterns must reject stage_metadata qty siblings."""
    from app.specs.identifiers import QUANTITY_SPEC

    anti_patterns_lower = " ".join(QUANTITY_SPEC.anti_patterns).lower()
    assert "cut" in anti_patterns_lower
    assert "shipped" in anti_patterns_lower or "sewn" in anti_patterns_lower


def test_date_trio_aliases_include_recent_additions() -> None:
    """Shipment 'ex con' and ex_fty 'ex fac' aliases must be present."""
    from app.specs.identifiers import EX_FTY_DATE_SPEC, SHIPMENT_DATE_SPEC

    assert any("ex con" in a.lower() for a in SHIPMENT_DATE_SPEC.aliases)
    assert any("ex fac" in a.lower() for a in EX_FTY_DATE_SPEC.aliases)
