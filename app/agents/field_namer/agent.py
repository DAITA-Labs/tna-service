"""FieldNamer Agent — maps detected labels and stage headers to canonical names."""
from __future__ import annotations

from typing import Any

from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
from app.agents.field_namer.tuning import FieldNamerTuning
from app.agents.field_namer.validators import validate_canonical_name_map
from app.enums.pli_mode import PliMode
from app.models.artifacts import SheetPlan, StageBandSpec, StageColumn
from app.prompts import FIELD_NAMER


class FieldNamerAgent(Agent):
    """Single-call LLM agent: SheetPlan -> CanonicalNameMap.

    Multi-channel input: reads identity from header_labels (ROW_PER_PLI),
    kv_anchors (SHEET_IS_PLI), or pli_blocks[].identity (SECTION_PER_PLI).
    Stage columns from sheet-level + block-level bands. For ROW_PER_PLI,
    samples up to 3 values per identity label from the workbook.
    """

    name = "field_namer"
    prompt = FIELD_NAMER
    output_schema = CanonicalNameMap
    tuning = FieldNamerTuning()

    def build_input(self, ctx: Any, inputs: FieldNamerInputs) -> str:
        """Assemble the prompt body symmetrically across pli_modes."""
        plan = inputs.plan
        ws = ctx.wb[plan.sheet] if hasattr(ctx, "wb") else None

        identity = self._collect_identity(plan)
        stage_names, sub_field_labels = self._collect_stage_channels(plan)
        samples = (
            _sample_values(ws, plan, identity, k=3)
            if ws is not None else {}
        )
        return _format_markdown(plan.sheet, identity, stage_names, sub_field_labels, samples)

    def validate_input(self, user_text: str) -> InputVerdict:
        """No-op input validation — Pydantic guards the structural shape."""
        return InputVerdict.ok()

    def validate_output(self, output: CanonicalNameMap, ctx: Any) -> OutputVerdict:
        """Delegate to the canonical-allow-list validator (uses self.tuning)."""
        return validate_canonical_name_map(output, ctx, tuning=self.tuning)

    def _collect_identity(self, plan: SheetPlan) -> list[tuple[str, str]]:
        """Gather identity (raw_label, column_letter) tuples from all three channels."""
        identity: list[tuple[str, str]] = [(hl.raw, hl.col) for hl in plan.header_labels]
        identity.extend((kv.field, _col_of(kv.label_cell)) for kv in plan.kv_anchors)
        for blk in plan.pli_blocks:
            identity.extend((kv.field, _col_of(kv.label_cell)) for kv in blk.identity)
        return identity

    def _collect_stage_channels(self, plan: SheetPlan) -> tuple[list[str], set[str]]:
        """Gather stage names + sub-field labels from sheet-level and block-level bands."""
        stage_names: list[str] = []
        sub_field_labels: set[str] = set()
        all_bands = list(plan.stage_bands)
        for blk in plan.pli_blocks:
            all_bands.extend(blk.stage_bands)
        for band in all_bands:
            for sc in band.stage_columns or _legacy_columns(band):
                stage_names.append(sc.name)
                sub_field_labels.update(sc.sub_columns.keys())
        return stage_names, sub_field_labels


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


def _format_markdown(
    sheet: str, identity: list[tuple[str, str]],
    stage_names: list[str], sub_field_labels: set[str],
    samples: dict[str, list[object]],
) -> str:
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


def _sample_values(
    ws, plan: SheetPlan, identity: list[tuple[str, str]],
    k: int = 3,
) -> dict[str, list[object]]:
    """Return up to `k` non-null sample values per identity label.

    For ROW_PER_PLI: reads data rows from `plan.rows` (ANCHOR/CHILD).
    Other modes: returns {} — KV labels carry their own values.
    String values are truncated to 60 chars to keep prompt size bounded.
    """
    if plan.pli_mode is not PliMode.ROW_PER_PLI:
        return {}
    data_rows = [
        r.idx for r in plan.rows
        if r.role.value in {"anchor", "child"}
    ]
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
