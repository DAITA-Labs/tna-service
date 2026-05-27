"""app.specs — single source of truth for the 3-area extraction design.

This package holds spec dataclasses + registries for the canvas architecture's
deterministic matching layer and judge-prompt inputs. One spec drives BOTH:

  - the deterministic matcher (alias lookup, dtype gate, anti-pattern reject)
  - the LLM judge prompt (description, patterns, anti-patterns, examples)

Module map:
  enums.py       core enums (PliMode, Area, LabelMatchMode, ValueDtype, ...)
  _base.py       dataclasses (FieldSpec, StageSpec, SubfieldSpec, ValueConstraints)
  identifiers.py 11 identifier FieldSpec instances + IDENTIFIER_SPECS registry
  stages.py      stage StageSpec instances + STAGE_SPECS registry
  subfields.py   sub-field SubfieldSpec instances + SUBFIELD_SPECS registry
  metadata.py    metadata FieldSpec instances + METADATA_SPECS registry
  schemas.py     Pydantic input/output schemas for every judge

Prompt templates and renderers live separately under experiments/specs/ for now;
Tier 6 (judges) relocates them to app/prompts/ + app/tools/render/ per ADR-0007.

Usage:
  from app.specs import IO_NUMBER_SPEC, IDENTIFIER_SPECS, FieldSpec
"""
from __future__ import annotations

from app.specs._base import (
    FieldSpec,
    StageSpec,
    SubfieldSpec,
    ValueConstraints,
)
from app.specs.enums import (
    Area,
    CheckOutcome,
    ClassificationCheck,
    FieldConfidence,
    FieldScope,
    JudgeType,
    LabelMatchMode,
    PhaseAction,
    PliAxis,
    PliMode,
    ReadDirection,
    ValueDtype,
    ValueDtypeMode,
    ValuePattern,
    Verdict,
)
from app.specs.identifiers import (
    COLOR_CODE_SPEC,
    COLOR_NAME_SPEC,
    DATE_IDENTIFIERS_AT_LEAST_ONE,
    DELIVERY_DATE_SPEC,
    EX_FTY_DATE_SPEC,
    FABRIC_CODE_SPEC,
    FABRIC_NAME_SPEC,
    IDENTIFIER_CANONICALS,
    IDENTIFIER_SPECS,
    IO_NUMBER_SPEC,
    MANDATORY_IDENTIFIERS,
    QUANTITY_SPEC,
    SHIPMENT_DATE_SPEC,
    STYLE_CODE_SPEC,
    STYLE_NAME_SPEC,
    get_identifier_spec,
)
from app.specs.metadata import (
    BUYER_SPEC,
    FACTORY_SPEC,
    METADATA_CANONICALS,
    METADATA_SPECS,
    ORDER_RECEIPT_DATE_SPEC,
    SEASON_SPEC,
    get_metadata_spec,
)
from app.specs.schemas import (
    ClassificationJudgeInput,
    ClassificationJudgeOutput,
    DetectedBand,
    FieldFindingJudgeInput,
    FieldFindingJudgeOutput,
    FieldLocator,
    FinalFinding,
    FinalStage,
    FindingForJudge,
    FindingWithJudgment,
    JudgmentRec,
    MetadataEntry,
    MetadataKVJudgeInput,
    MetadataKVJudgeOutput,
    PhaseIdentifierJudgeInput,
    PhaseIdentifierJudgeOutput,
    PhaseMetadataJudgeInput,
    PhaseMetadataJudgeOutput,
    PhaseStageJudgeInput,
    PhaseStageJudgeOutput,
    PliEnumerationPlan,
    PliGroup,
    ReadPattern,
    SampleCell,
    SampleRow,
    SheetLevelPlan,
    SheetSample,
    SpecSummary,
    StageBandJudgeInput,
    StageBandJudgeOutput,
    StageLocator,
    StageStrip,
    SubColumnRef,
)
from app.specs.stages import (
    CUTTING_SPEC,
    EX_FACTORY_SHIPMENT_SPEC,
    FABRIC_SPEC,
    FEEDING_SPEC,
    FINAL_INSPECTION_SPEC,
    FIT_APPROVAL_SPEC,
    FIT_SEND_SPEC,
    IN_HOUSE_FABRIC_SEND_SPEC,
    LINE_PLAN_SPEC,
    PRE_PRODUCTION_SEND_SPEC,
    SEWING_END_SPEC,
    SEWING_SPEC,
    SEWING_START_SPEC,
    SIZESET_SUBMISSION_SPEC,
    STAGE_CANONICALS,
    STAGE_SPECS,
    VAP_SPEC,
    get_stage_spec,
)
from app.specs.subfields import (
    ACTUAL_DATE_SPEC,
    APPROVAL_DATE_SPEC,
    APPROVED_QTY_SPEC,
    END_DATE_SPEC,
    PLANNED_DATE_SPEC,
    QUANTITY_SUBFIELD_SPEC,
    RECEIVED_DATE_SPEC,
    REMARKS_SPEC,
    START_DATE_SPEC,
    STATUS_SPEC,
    SUBFIELD_CANONICALS,
    SUBFIELD_SPECS,
    get_subfield_spec,
)

__all__ = [
    # ─ Enums ────────────────────────────────────────────────────────────
    "Area", "CheckOutcome", "ClassificationCheck", "FieldConfidence",
    "FieldScope", "JudgeType", "LabelMatchMode", "PhaseAction",
    "PliAxis", "PliMode", "ReadDirection",
    "ValueDtype", "ValueDtypeMode", "ValuePattern", "Verdict",

    # ─ Spec dataclasses ─────────────────────────────────────────────────
    "FieldSpec", "StageSpec", "SubfieldSpec", "ValueConstraints",

    # ─ Identifier specs ─────────────────────────────────────────────────
    "IDENTIFIER_SPECS", "IDENTIFIER_CANONICALS",
    "MANDATORY_IDENTIFIERS", "DATE_IDENTIFIERS_AT_LEAST_ONE",
    "IO_NUMBER_SPEC", "QUANTITY_SPEC",
    "STYLE_CODE_SPEC", "STYLE_NAME_SPEC",
    "COLOR_CODE_SPEC", "COLOR_NAME_SPEC",
    "FABRIC_CODE_SPEC", "FABRIC_NAME_SPEC",
    "DELIVERY_DATE_SPEC", "SHIPMENT_DATE_SPEC", "EX_FTY_DATE_SPEC",
    "get_identifier_spec",

    # ─ Stage specs ──────────────────────────────────────────────────────
    "STAGE_SPECS", "STAGE_CANONICALS", "get_stage_spec",
    "FABRIC_SPEC", "IN_HOUSE_FABRIC_SEND_SPEC",
    "PRE_PRODUCTION_SEND_SPEC", "SIZESET_SUBMISSION_SPEC",
    "CUTTING_SPEC", "SEWING_SPEC", "SEWING_START_SPEC", "SEWING_END_SPEC",
    "FIT_SEND_SPEC", "FIT_APPROVAL_SPEC",
    "FINAL_INSPECTION_SPEC", "EX_FACTORY_SHIPMENT_SPEC",
    "VAP_SPEC", "LINE_PLAN_SPEC", "FEEDING_SPEC",

    # ─ Sub-field specs ──────────────────────────────────────────────────
    "SUBFIELD_SPECS", "SUBFIELD_CANONICALS", "get_subfield_spec",
    "PLANNED_DATE_SPEC", "ACTUAL_DATE_SPEC", "APPROVAL_DATE_SPEC",
    "RECEIVED_DATE_SPEC", "START_DATE_SPEC", "END_DATE_SPEC",
    "APPROVED_QTY_SPEC", "QUANTITY_SUBFIELD_SPEC",
    "REMARKS_SPEC", "STATUS_SPEC",

    # ─ Metadata specs ───────────────────────────────────────────────────
    "METADATA_SPECS", "METADATA_CANONICALS", "get_metadata_spec",
    "BUYER_SPEC", "SEASON_SPEC", "FACTORY_SPEC",
    "ORDER_RECEIPT_DATE_SPEC",

    # ─ Schemas ──────────────────────────────────────────────────────────
    "ClassificationJudgeInput", "ClassificationJudgeOutput",
    "DetectedBand",
    "FieldFindingJudgeInput", "FieldFindingJudgeOutput",
    "FieldLocator",
    "FinalFinding", "FinalStage",
    "FindingForJudge", "FindingWithJudgment",
    "JudgmentRec", "MetadataEntry",
    "MetadataKVJudgeInput", "MetadataKVJudgeOutput",
    "PhaseIdentifierJudgeInput", "PhaseIdentifierJudgeOutput",
    "PhaseMetadataJudgeInput", "PhaseMetadataJudgeOutput",
    "PhaseStageJudgeInput", "PhaseStageJudgeOutput",
    "PliEnumerationPlan", "PliGroup",
    "ReadPattern", "SampleCell", "SampleRow",
    "SheetLevelPlan", "SheetSample",
    "SpecSummary",
    "StageBandJudgeInput", "StageBandJudgeOutput",
    "StageLocator", "StageStrip", "SubColumnRef",
]
