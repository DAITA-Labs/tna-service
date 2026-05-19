"""FieldNamer agent — maps detected labels and stage column headers to canonical field names."""
from __future__ import annotations

from pathlib import Path

from haystack import component
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string

from app.core.logs import get_logger
from app.core.prompt_loader import load_prompt
from app.enums.pli_mode import PliMode
from app.models.artifacts import (
    CanonicalNameMap, KVAnchor, SheetPlan, StageBandSpec, StageColumn,
)
from app.services.agents._base import AgentRunFailure, AgentRunner, AgentSpec
from app.services.llm_provider import LLMProvider

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: object, inputs: dict) -> str:
    """Assemble the LLM prompt body from all identity + stage channels.

    Reads symmetrically across the three pli_modes:
      ROW_PER_PLI     → plan.header_labels
      SHEET_IS_PLI    → plan.kv_anchors
      SECTION_PER_PLI → plan.pli_blocks[].identity
    Stage names + sub-field labels come from stage_columns on both sheet-level
    and block-level stage bands. For ROW_PER_PLI, also pulls 3 sample values per
    identity label from the workbook so the LLM can infer canonical names from
    values when prompt vocab doesn't match.
    """
    plan: SheetPlan = inputs["plan"]
    ws = ctx.wb[plan.sheet] if hasattr(ctx, "wb") else None

    identity: list[tuple[str, str]] = [(hl.raw, hl.col) for hl in plan.header_labels]
    identity.extend((kv.field, _col_of(kv.label_cell)) for kv in plan.kv_anchors)
    for blk in plan.pli_blocks:
        identity.extend((kv.field, _col_of(kv.label_cell)) for kv in blk.identity)

    stage_names: list[str] = []
    sub_field_labels: set[str] = set()
    all_bands = list(plan.stage_bands)
    for blk in plan.pli_blocks:
        all_bands.extend(blk.stage_bands)
    for band in all_bands:
        for sc in band.stage_columns or _legacy_columns(band):
            stage_names.append(sc.name)
            sub_field_labels.update(sc.sub_columns.keys())

    samples = _sample_values(ws, plan, identity, k=3) if ws is not None else {}
    return _format_markdown(plan.sheet, identity, stage_names, sub_field_labels, samples)


def _col_of(addr: str) -> str:
    """Return the column letter from a cell address like 'AA12'."""
    col_letter, _ = coordinate_from_string(addr)
    return col_letter


def _legacy_columns(band: StageBandSpec) -> list[StageColumn]:
    """Build StageColumn list from a band's legacy `stage_cols` dict."""
    return [
        StageColumn(name=name, name_cell=f"{col}{band.sub_header_row}",
                     primary_col=col)
        for name, col in band.stage_cols.items()
    ]


def _format_markdown(sheet: str, identity: list[tuple[str, str]],
                     stage_names: list[str], sub_field_labels: set[str],
                     samples: dict[str, list[object]]) -> str:
    """Render a deterministic markdown prompt body."""
    lines = [f"# Sheet: {sheet}", "", "## Identity labels detected:"]
    for raw, col in sorted(set(identity)):
        sample_blurb = ""
        if samples.get(raw):
            sample_blurb = "  samples: " + ", ".join(
                repr(s) for s in samples[raw][:3]
            )
        lines.append(f"  - {raw!r} (col {col}){sample_blurb}")
    lines.append("")
    lines.append("## Stage headers detected:")
    for name in sorted(set(stage_names)):
        lines.append(f"  - {name!r}")
    if sub_field_labels:
        lines.append("")
        lines.append("## Stage sub-field labels detected:")
        for sub in sorted(sub_field_labels):
            lines.append(f"  - {sub!r}")
    return "\n".join(lines)


def _sample_values(ws, plan: SheetPlan, identity: list[tuple[str, str]],
                   k: int = 3) -> dict[str, list[object]]:
    """Return up to `k` non-null sample values per identity label.

    For ROW_PER_PLI: reads data rows from `plan.rows` (ANCHOR/CHILD).
    For SHEET_IS_PLI / SECTION_PER_PLI: returns {} — KV labels carry their own
    values, no sampling needed.
    String values are truncated to 60 chars to keep prompt size bounded.
    """
    if plan.pli_mode is not PliMode.ROW_PER_PLI:
        return {}
    data_rows = [r.idx for r in plan.rows
                 if r.role.value in {"anchor", "child"}]
    if not data_rows:
        return {}
    out: dict[str, list[object]] = {}
    for raw, col in identity:
        col_idx = column_index_from_string(col)
        seen: list[object] = []
        for r in data_rows:
            if len(seen) >= k:
                break
            v = ws.cell(row=r, column=col_idx).value
            if v is None:
                continue
            if isinstance(v, str) and len(v) > 60:
                v = v[:57] + "..."
            seen.append(v)
        if seen:
            out[raw] = seen
    return out


SPEC = AgentSpec(
    name="field_namer",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "field_namer.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=CanonicalNameMap,
    build_user_input=_build_user_input,
)


@component
class FieldNamer:
    """Haystack component that resolves raw cell labels to canonical field names.

    Accepts a SheetPlan and produces a CanonicalNameMap; fires once per sheet
    during the field-naming phase of the pipeline.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Wire up the underlying AgentRunner with the field_namer spec."""
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(name_map=CanonicalNameMap)
    def run(self, workbook_ctx: object, plan: SheetPlan) -> dict:
        """Run the field-namer agent and return a canonical name mapping.

        Falls back to an empty CanonicalNameMap on agent failure so the
        pipeline can continue with best-effort names.
        """
        result = self.runner.run(workbook_ctx, {"plan": plan})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="field_namer")
            return {"name_map": CanonicalNameMap()}
        return {"name_map": result}
