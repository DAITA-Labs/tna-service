"""Top-level orchestration — Phase 0..7 from the spec.

D1 Sequential per sheet; D2 Locators in parallel within a sheet; D3
one_sheet_per_pli fast-path break; D4 Validation after aggregation;
D5 1-retry-with-context (in AgentRunner); D6 Tiered failure handling;
D7 No skip-list adaptive routing; D8 Concatenate cross-sheet PLIs,
preserve source_sheet; D9 Determinism gates in applier; D10 Per-agent
+ per-validator telemetry.
"""
from __future__ import annotations
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.repositories.workbook_repo import register_workbook
from app.models.extraction import ExtractionResult, PLI, Warning
from app.models.artifacts import (
    StructuralFingerprint, PLIBoundaries, FieldMap, ValidationFindings,
)
from app.enums.boundary_pattern import BoundaryPattern
from app.services.llm_provider import AnthropicProvider
from app.services.agents.sheet_classifier import SheetClassifier
from app.services.agents.layout_fingerprinter import LayoutFingerprinter
from app.services.agents.boundary_finder import BoundaryFinder
from app.services.agents.identity_locator import IdentityLocator
from app.services.agents.quantity_date_locator import QuantityDateLocator
from app.services.agents.stage_locator import StageLocator
from app.services.applier.field_applier import apply_field_map, is_real_pli
from app.services.applier.stage_applier import (
    apply_stage_band_set, strip_stage_columns_from_metadata,
)
from app.services.validation.source_cell_verifier import SourceCellVerifier
from app.services.validation.header_match_verifier import HeaderMatchVerifier
from app.services.validation.coverage_verifier import CoverageVerifier
from app.services.validation.field_dropout_verifier import FieldDropoutVerifier
from app.services.reconciler import reconcile
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.logs import get_logger
from app.core.telemetry import extraction_duration_seconds, extraction_pli_count
# Import-side-effect: register tool functions + pattern handlers.
import app.repositories.workbook_tools.survey  # noqa: F401
import app.repositories.workbook_tools.bulk_read  # noqa: F401
import app.repositories.workbook_tools.targeted  # noqa: F401
import app.repositories.workbook_tools.structure  # noqa: F401
import app.repositories.workbook_tools.search  # noqa: F401
import app.services.applier.patterns  # noqa: F401

log = get_logger(__name__)


def _merge_field_maps(maps: list[FieldMap]) -> FieldMap:
    """Concatenate locations + metadata_locations across multiple FieldMaps."""
    if not maps:
        return FieldMap(sheet="")
    locs, mlocs = [], []
    sheet = maps[0].sheet
    for m in maps:
        locs.extend(m.locations)
        mlocs.extend(m.metadata_locations)
    return FieldMap(sheet=sheet, locations=locs, metadata_locations=mlocs)


def _describe_format(fp: StructuralFingerprint | None) -> str:
    if fp is None:
        return "unknown"
    if fp.sheets_appear_parallel:
        return "one_sheet_per_pli"
    if fp.has_vertical_merges_in_data:
        return "vertical_merge"
    if fp.has_totals_rows:
        return "data_then_total"
    if fp.has_scattered_metadata and fp.multi_band_stages_per_pli:
        return "orders_plan"
    return "tabular_columnar"


def extract(workbook_path: Path | str, *, llm=None) -> ExtractionResult:
    """End-to-end orchestrated extraction."""
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()
    warnings: list[Warning] = []

    # Phase 0 - workbook summary.
    summary = TOOL_REGISTRY.get("workbook_summary")(ctx)

    # Phase 1 - sheet classification.
    sc = SheetClassifier(llm=llm)
    relevant = sc.run(workbook_ctx=ctx, workbook_summary=summary)["relevant_sheets"]
    if not relevant:
        return ExtractionResult(
            plis=[], source_file=str(ctx.path),
            warnings=[Warning(message="No relevant sheets identified",
                              severity="warning")],
        )

    fp_agent = LayoutFingerprinter(llm=llm)
    bf_agent = BoundaryFinder(llm=llm)
    il_agent = IdentityLocator(llm=llm)
    qd_agent = QuantityDateLocator(llm=llm)
    sl_agent = StageLocator(llm=llm)

    all_plis: list[PLI] = []
    all_boundaries: list[PLIBoundaries] = []
    fp: StructuralFingerprint | None = None

    for sheet in relevant:
        # Phase 2 — fingerprint.
        fp = fp_agent.run(workbook_ctx=ctx, sheet=sheet)["fingerprint"]

        # Phase 3 — boundary.
        boundaries = bf_agent.run(
            workbook_ctx=ctx, sheet=sheet, fingerprint=fp,
        )["boundaries"]
        all_boundaries.append(boundaries)

        # Phase 4 — locators in parallel (D2).
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_id = pool.submit(il_agent.run, workbook_ctx=ctx, sheet=sheet,
                              boundaries=boundaries)
            f_qd = pool.submit(qd_agent.run, workbook_ctx=ctx, sheet=sheet,
                              boundaries=boundaries)
            f_st = pool.submit(sl_agent.run, workbook_ctx=ctx, sheet=sheet,
                              fingerprint=fp, boundaries=boundaries)
            fm_id = f_id.result()["field_map"]
            fm_qd = f_qd.result()["field_map"]
            sbs = f_st.result()["stage_band_set"]

        # Merge field maps; dedup metadata against stage columns.
        fm = _merge_field_maps([fm_id, fm_qd])
        fm = strip_stage_columns_from_metadata(fm, sbs)

        # Phase 5 — apply (deterministic).
        plis = apply_field_map(ctx, sheet, fm, boundaries)
        stages_per_pli = apply_stage_band_set(ctx, sheet, sbs, boundaries)
        for pli, stages in zip(plis, stages_per_pli):
            pli.stages = stages
            if pli.source_sheet is None:
                pli.source_sheet = sheet

        # D9 deterministic filter — drop rows with no canonical identity.
        kept = [(p, s) for p, s in zip(plis, stages_per_pli) if is_real_pli(p)]
        all_plis.extend(p for p, _ in kept)
        log.info("sheet_processed", sheet=sheet, kept=len(kept),
                 dropped=len(plis) - len(kept))

        # D3 fast-path break: one_sheet_per_pli covers the whole workbook.
        if boundaries.pattern == BoundaryPattern.ONE_SHEET_PER_PLI:
            log.info("one_sheet_per_pli_break", remaining_skipped=True)
            break

    # Phase 6 — validation (D4: after all sheets aggregated).
    workflow_result = ExtractionResult(
        plis=all_plis, warnings=warnings,
        format_detected=_describe_format(fp),
        source_file=str(ctx.path),
    )
    src_v = SourceCellVerifier(workbook_ctx=ctx).run(extraction=workflow_result)["findings"]
    hdr_v = HeaderMatchVerifier(workbook_ctx=ctx).run(extraction=workflow_result)["findings"]
    cov_v = CoverageVerifier(boundaries=all_boundaries).run(extraction=workflow_result)["findings"]
    drop_v = FieldDropoutVerifier().run(extraction=workflow_result)["findings"]
    all_findings = ValidationFindings(findings=(
        src_v.findings + hdr_v.findings + cov_v.findings + drop_v.findings
    ))

    # Phase 7 — reconcile.
    final = reconcile(workflow_out=workflow_result, validation_out=all_findings)

    # Telemetry.
    extraction_duration_seconds.labels(
        format_detected=final.format_detected or "unknown"
    ).observe(time.monotonic() - t0)
    extraction_pli_count.labels(source_file=ctx.path.name).set(len(final.plis))

    return final
