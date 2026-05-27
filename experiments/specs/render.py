"""Prompt renderers — fill prompt templates with spec data + finding context.

Each renderer pulls patterns/anti-patterns/examples from the corresponding
spec and formats them as bullet lists, then fills the template. Update a
spec → next render reflects the change. No prompt strings duplicated.
"""
from __future__ import annotations

from typing import Any

from . import prompts
from ._base import FieldSpec, StageSpec, SubfieldSpec
from .schemas import (
    ClassificationJudgeInput,
    FieldFindingJudgeInput,
    FindingForJudge,
    FindingWithJudgment,
    MetadataKVJudgeInput,
    PhaseIdentifierJudgeInput,
    PhaseMetadataJudgeInput,
    PhaseStageJudgeInput,
    SheetSample,
    SpecSummary,
    StageBandJudgeInput,
)


# =============================================================================
# Spec → SpecSummary (compact view passed to judges)
# =============================================================================


def spec_summary_for_field(spec: FieldSpec) -> SpecSummary:
    return SpecSummary(
        canonical=spec.canonical,
        description=spec.description,
        patterns=list(spec.patterns),
        anti_patterns=list(spec.anti_patterns),
        examples=list(spec.examples),
        mandatory=spec.mandatory,
    )


def spec_summary_for_stage(spec: StageSpec) -> SpecSummary:
    return SpecSummary(
        canonical=spec.canonical,
        description=spec.description,
        patterns=list(spec.patterns),
        anti_patterns=list(spec.anti_patterns),
        examples=list(spec.examples),
        mandatory=False,
    )


def spec_summary_for_subfield(spec: SubfieldSpec) -> SpecSummary:
    return SpecSummary(
        canonical=spec.canonical,
        description=spec.description,
        patterns=list(spec.patterns),
        anti_patterns=list(spec.anti_patterns),
        examples=list(spec.examples),
        mandatory=False,
    )


# =============================================================================
# Bullet helpers
# =============================================================================


def _bullets(items: list[str], empty: str = "  (none)") -> str:
    if not items:
        return empty
    return "\n".join(f"  - {item}" for item in items)


def _render_sheet_sample(sample: SheetSample | None) -> str:
    """Render a SheetSample as a fixed-width text grid the LLM can read.

    Format:
        col→    A           B           C
        row 3   "Buyer:"    "XYZ"       ""
        row 4   "IO No"     "1063"      ""
        ...
        [truncated — full sheet is N×M]
    """
    if sample is None:
        return "  (no sheet sample provided)"
    if not sample.rows:
        return "  (sheet sample is empty)"

    # Collect all columns referenced across rows so column order is stable
    columns_in_use: list[str] = []
    seen: set[str] = set()
    for r in sample.rows:
        for c in r.cells:
            if c.column not in seen:
                seen.add(c.column)
                columns_in_use.append(c.column)

    # Header line
    col_width = 14
    header = " " * 8 + "".join(f"{c:<{col_width}}" for c in columns_in_use)
    lines = [header]
    for r in sample.rows:
        # Map column → cell for fast lookup in this row
        by_col = {c.column: c for c in r.cells}
        row_cells = []
        for col in columns_in_use:
            c = by_col.get(col)
            if c is None or c.value in (None, ""):
                row_cells.append(f"{'':<{col_width}}")
            else:
                text = str(c.value)
                if len(text) > col_width - 2:
                    text = text[: col_width - 3] + "…"
                marker = ""
                if c.is_merged:
                    marker += "m"
                if c.is_bold:
                    marker += "b"
                if marker:
                    text = f"{text}{{{marker}}}"
                row_cells.append(f'"{text}"'[: col_width - 1].ljust(col_width))
        lines.append(f"row {r.row_number:>3}  " + "".join(row_cells))

    if sample.truncated:
        lines.append(
            f"  [truncated — full sheet is {sample.full_row_count}×{sample.full_col_count}]"
        )
    return "\n".join(lines)


# =============================================================================
# Renderers — one per judge prompt
# =============================================================================


def render_field_finding_judge_prompt(inp: FieldFindingJudgeInput) -> str:
    s = inp.spec_summary
    f = inp.finding
    return prompts.FIELD_FINDING_JUDGE_PROMPT.format(
        canonical=s.canonical,
        description=s.description,
        mandatory="yes" if s.mandatory else "no",
        patterns_bullets=_bullets(s.patterns),
        anti_patterns_bullets=_bullets(s.anti_patterns),
        examples_bullets=_bullets(s.examples),
        pattern_used=f.pattern_used,
        label_cell=f.label_cell,
        label_text=f.label_text,
        value_cell=f.value_cell,
        value=str(f.value),
        value_dtype_observed=f.value_dtype_observed,
        confidence=f"{f.confidence:.2f}",
        evidence_bullets=_bullets(f.evidence),
        competing_bullets=_bullets(f.competing_candidates, empty="  (none)"),
        sheet_sample_block=_render_sheet_sample(inp.sheet_sample),
    )


def render_phase_identifier_judge_prompt(
    inp: PhaseIdentifierJudgeInput,
    max_iterations: int = 2,
) -> str:
    findings_block = _render_findings_with_judgments_block(inp.findings_with_judgments)
    mandatory_block = _bullets(inp.mandatory_canonicals)
    return prompts.PHASE_IDENTIFIER_JUDGE_PROMPT.format(
        pli_mode=inp.pli_mode.value if inp.pli_mode else "<unknown>",
        iteration=inp.iteration,
        max_iterations=max_iterations,
        shape_brief=inp.shape_brief,
        mandatory_list=mandatory_block,
        findings_with_judgments_block=findings_block,
    )


def render_stage_band_judge_prompt(
    inp: StageBandJudgeInput,
    candidate_specs: list[StageSpec],
) -> str:
    band = inp.band
    strip = inp.strip
    candidates_block = _render_stage_candidates(candidate_specs)
    # Pull this band's header cells from the strip (just informational —
    # full row is also in the sheet_sample if provided).
    name_row_text_block = f"strip {strip.strip_index} name_row={strip.name_row} sub_label_row={strip.sub_label_row}"
    return prompts.STAGE_BAND_JUDGE_PROMPT.format(
        band_index=band.band_index,
        column_range=f"{band.column_range[0]}..{band.column_range[1]}",
        candidate_stage=band.name,
        name_row_text=name_row_text_block,
        plan_date_col=band.plan_date_col if band.plan_date_col is not None else "<not found>",
        confidence=f"{band.confidence:.2f}",
        evidence_bullets=_bullets(band.evidence),
        candidates_block=candidates_block,
        sheet_sample_block=_render_sheet_sample(inp.sheet_sample),
    )


def render_phase_stage_judge_prompt(
    inp: PhaseStageJudgeInput,
    max_iterations: int = 2,
) -> str:
    bands_block = "\n".join(
        f"- band {i}: {b}" for i, b in enumerate(inp.bands_with_judgments)
    )
    return prompts.PHASE_STAGE_JUDGE_PROMPT.format(
        pli_mode=inp.pli_mode.value if inp.pli_mode else "<unknown>",
        arena_bounds=str(inp.arena_bounds) if inp.arena_bounds else "<not detected>",
        iteration=inp.iteration,
        max_iterations=max_iterations,
        bands_with_judgments_block=bands_block,
    )


def render_metadata_kv_judge_prompt(
    inp: MetadataKVJudgeInput,
    candidate_specs: list[FieldSpec],
) -> str:
    candidates_block = _render_field_candidates(candidate_specs)
    return prompts.METADATA_KV_JUDGE_PROMPT.format(
        label_cell=inp.label_cell,
        label_text=inp.label_text,
        value_cell=inp.value_cell,
        value=str(inp.value),
        candidates_block=candidates_block,
        evidence_bullets=_bullets(inp.evidence),
    )


def render_phase_metadata_judge_prompt(
    inp: PhaseMetadataJudgeInput,
    max_iterations: int = 2,
) -> str:
    kvs_block = "\n".join(
        f"- kv {i}: {kv}" for i, kv in enumerate(inp.kvs_with_judgments)
    )
    return prompts.PHASE_METADATA_JUDGE_PROMPT.format(
        kvs_with_judgments_block=kvs_block,
    )


def render_classification_judge_prompt(inp: ClassificationJudgeInput) -> str:
    vote_block = "\n".join(
        f"  - {mode}: {score:.2f}"
        for mode, score in sorted(inp.vote_breakdown.items(), key=lambda kv: -kv[1])
    )
    evidence_block = "\n".join(
        f"  - {check}: {evidence}"
        for check, evidence in inp.evidence_per_check.items()
    )
    return prompts.CLASSIFICATION_JUDGE_PROMPT.format(
        shape_brief=inp.shape_brief,
        vote_breakdown_block=vote_block,
        evidence_per_check_block=evidence_block,
    )


# =============================================================================
# Sub-helpers
# =============================================================================


def _render_findings_with_judgments_block(
    items: list[FindingWithJudgment],
) -> str:
    if not items:
        return "  (no findings)"
    lines: list[str] = []
    for i, fwj in enumerate(items):
        f = fwj.finding
        lines.append(
            f"  [{i}] canonical={f.canonical}  cell={f.label_cell}->{f.value_cell}  "
            f"value={f.value!r}  conf={f.confidence:.2f}"
        )
        if fwj.judgment is not None:
            j = fwj.judgment
            target = f" target={j.target}" if j.target else ""
            lines.append(f"      judge: verdict={j.verdict.value}{target}  reason={j.reason!r}")
        else:
            lines.append("      judge: (not reviewed — confidence high enough)")
    return "\n".join(lines)


def _render_stage_candidates(specs: list[StageSpec]) -> str:
    if not specs:
        return "  (none)"
    lines: list[str] = []
    for spec in specs:
        lines.append(f"  - {spec.canonical}: {spec.description}")
        if spec.aliases:
            lines.append(f"      aliases: {', '.join(spec.aliases[:5])}")
    return "\n".join(lines)


def _render_field_candidates(specs: list[FieldSpec]) -> str:
    if not specs:
        return "  (none)"
    lines: list[str] = []
    for spec in specs:
        lines.append(f"  - {spec.canonical}: {spec.description}")
        if spec.aliases:
            lines.append(f"      aliases: {', '.join(spec.aliases[:5])}")
    return "\n".join(lines)
