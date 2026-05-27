"""experiments/specs — single source of truth for the 3-area extraction design.

Hierarchy of declarations:

  enums.py     ─→ PliMode, Area, LabelMatchMode, ValueDtype, ValueDtypeMode,
                  ValuePattern, Verdict, PhaseAction, FieldConfidence,
                  JudgeType, ClassificationCheck, CheckOutcome
  _base.py     ─→ FieldSpec, StageSpec, SubfieldSpec, ValueConstraints
  identifiers.py ─→ 9 identifier FieldSpec instances + IDENTIFIER_SPECS
  stages.py    ─→ 12 stage StageSpec instances + STAGE_SPECS
  subfields.py ─→ 9 sub-field SubfieldSpec instances + SUBFIELD_SPECS
  metadata.py  ─→ 6 metadata FieldSpec instances + METADATA_SPECS
  schemas.py   ─→ Pydantic input/output schemas for every judge
  prompts.py   ─→ Prompt templates for every judge
  render.py    ─→ Renderers that fill templates from spec + finding data

Usage:

  from experiments.specs import IO_NUMBER_SPEC, render_field_finding_judge_prompt
"""
from __future__ import annotations

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
from .enums import (
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

# -----------------------------------------------------------------------------
# Spec dataclasses
# -----------------------------------------------------------------------------
from ._base import (
    FieldSpec,
    StageSpec,
    SubfieldSpec,
    ValueConstraints,
)

# -----------------------------------------------------------------------------
# Identifier specs
# -----------------------------------------------------------------------------
from .identifiers import (
    COLOR_CODE_SPEC,
    COLOR_NAME_SPEC,
    DATE_IDENTIFIERS_AT_LEAST_ONE,
    DELIVERY_DATE_SPEC,
    EX_FTY_DATE_SPEC,
    FABRIC_CODE_SPEC,
    FABRIC_NAME_SPEC,
    IO_NUMBER_SPEC,
    IDENTIFIER_CANONICALS,
    IDENTIFIER_SPECS,
    MANDATORY_IDENTIFIERS,
    QUANTITY_SPEC,
    SHIPMENT_DATE_SPEC,
    STYLE_CODE_SPEC,
    STYLE_NAME_SPEC,
    get_identifier_spec,
)

# -----------------------------------------------------------------------------
# Stage specs
# -----------------------------------------------------------------------------
from .stages import (
    CUTTING_SPEC,
    EX_FACTORY_SHIPMENT_SPEC,
    FABRIC_SPEC,
    FINAL_INSPECTION_SPEC,
    FIT_APPROVAL_SPEC,
    FIT_SEND_SPEC,
    IN_HOUSE_FABRIC_SEND_SPEC,
    PRE_PRODUCTION_SEND_SPEC,
    SEWING_END_SPEC,
    SEWING_SPEC,
    SEWING_START_SPEC,
    SIZESET_SUBMISSION_SPEC,
    STAGE_CANONICALS,
    STAGE_SPECS,
    get_stage_spec,
)

# -----------------------------------------------------------------------------
# Sub-field specs
# -----------------------------------------------------------------------------
from .subfields import (
    ACTUAL_DATE_SPEC,
    APPROVAL_DATE_SPEC,
    APPROVED_QTY_SPEC,
    END_DATE_SPEC,
    PLANNED_DATE_SPEC,
    QUANTITY_SUBFIELD_SPEC,
    RECEIVED_DATE_SPEC,
    REMARKS_SPEC,
    START_DATE_SPEC,
    SUBFIELD_CANONICALS,
    SUBFIELD_SPECS,
    get_subfield_spec,
)

# -----------------------------------------------------------------------------
# Metadata specs
# -----------------------------------------------------------------------------
from .metadata import (
    BUYER_SPEC,
    FACTORY_SPEC,
    METADATA_CANONICALS,
    METADATA_SPECS,
    ORDER_RECEIPT_DATE_SPEC,
    SEASON_SPEC,
    get_metadata_spec,
)

# -----------------------------------------------------------------------------
# Schemas (Pydantic — input/output contracts for judges)
# -----------------------------------------------------------------------------
from .schemas import (
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

# -----------------------------------------------------------------------------
# Prompts (templates)
# -----------------------------------------------------------------------------
from .prompts import (
    CLASSIFICATION_JUDGE_PROMPT,
    FIELD_FINDING_JUDGE_PROMPT,
    METADATA_KV_JUDGE_PROMPT,
    PHASE_IDENTIFIER_JUDGE_PROMPT,
    PHASE_METADATA_JUDGE_PROMPT,
    PHASE_STAGE_JUDGE_PROMPT,
    STAGE_BAND_JUDGE_PROMPT,
)

# -----------------------------------------------------------------------------
# Renderers
# -----------------------------------------------------------------------------
from .render import (
    render_classification_judge_prompt,
    render_field_finding_judge_prompt,
    render_metadata_kv_judge_prompt,
    render_phase_identifier_judge_prompt,
    render_phase_metadata_judge_prompt,
    render_phase_stage_judge_prompt,
    render_stage_band_judge_prompt,
    spec_summary_for_field,
    spec_summary_for_stage,
    spec_summary_for_subfield,
)


__all__ = [
    # Enums
    "Area", "CheckOutcome", "ClassificationCheck", "FieldConfidence",
    "JudgeType", "LabelMatchMode", "PhaseAction", "PliMode",
    "ValueDtype", "ValueDtypeMode", "ValuePattern", "Verdict",
    # Spec dataclasses
    "FieldSpec", "StageSpec", "SubfieldSpec", "ValueConstraints",
    # Identifier specs
    "IDENTIFIER_SPECS", "IDENTIFIER_CANONICALS", "MANDATORY_IDENTIFIERS",
    "DATE_IDENTIFIERS_AT_LEAST_ONE",
    "IO_NUMBER_SPEC", "QUANTITY_SPEC", "STYLE_CODE_SPEC", "STYLE_NAME_SPEC",
    "COLOR_CODE_SPEC", "COLOR_NAME_SPEC", "FABRIC_CODE_SPEC",
    "FABRIC_NAME_SPEC", "DELIVERY_DATE_SPEC", "SHIPMENT_DATE_SPEC",
    "EX_FTY_DATE_SPEC", "get_identifier_spec",
    # Stage specs
    "STAGE_SPECS", "STAGE_CANONICALS", "get_stage_spec",
    "FABRIC_SPEC", "IN_HOUSE_FABRIC_SEND_SPEC", "PRE_PRODUCTION_SEND_SPEC",
    "SIZESET_SUBMISSION_SPEC", "CUTTING_SPEC", "SEWING_SPEC",
    "SEWING_START_SPEC", "SEWING_END_SPEC", "FIT_SEND_SPEC",
    "FIT_APPROVAL_SPEC", "FINAL_INSPECTION_SPEC", "EX_FACTORY_SHIPMENT_SPEC",
    # Sub-field specs
    "SUBFIELD_SPECS", "SUBFIELD_CANONICALS", "get_subfield_spec",
    "PLANNED_DATE_SPEC", "ACTUAL_DATE_SPEC", "APPROVAL_DATE_SPEC",
    "RECEIVED_DATE_SPEC", "START_DATE_SPEC", "END_DATE_SPEC",
    "APPROVED_QTY_SPEC", "QUANTITY_SUBFIELD_SPEC", "REMARKS_SPEC",
    # Metadata specs
    "METADATA_SPECS", "METADATA_CANONICALS", "get_metadata_spec",
    "BUYER_SPEC", "SEASON_SPEC", "FACTORY_SPEC",
    "EX_FACTORY_DATE_SPEC", "ORDER_RECEIPT_DATE_SPEC",
    # Schemas
    "ClassificationJudgeInput", "ClassificationJudgeOutput",
    "FieldFindingJudgeInput", "FieldFindingJudgeOutput",
    "FinalFinding", "FinalStage", "FindingForJudge", "FindingWithJudgment",
    "JudgmentRec", "MetadataEntry",
    "MetadataKVJudgeInput", "MetadataKVJudgeOutput",
    "PhaseIdentifierJudgeInput", "PhaseIdentifierJudgeOutput",
    "PhaseMetadataJudgeInput", "PhaseMetadataJudgeOutput",
    "PhaseStageJudgeInput", "PhaseStageJudgeOutput",
    "SpecSummary", "StageBandJudgeInput", "StageBandJudgeOutput",
    # Prompts
    "CLASSIFICATION_JUDGE_PROMPT", "FIELD_FINDING_JUDGE_PROMPT",
    "METADATA_KV_JUDGE_PROMPT", "PHASE_IDENTIFIER_JUDGE_PROMPT",
    "PHASE_METADATA_JUDGE_PROMPT", "PHASE_STAGE_JUDGE_PROMPT",
    "STAGE_BAND_JUDGE_PROMPT",
    # Renderers
    "render_classification_judge_prompt",
    "render_field_finding_judge_prompt",
    "render_metadata_kv_judge_prompt",
    "render_phase_identifier_judge_prompt",
    "render_phase_metadata_judge_prompt",
    "render_phase_stage_judge_prompt",
    "render_stage_band_judge_prompt",
    "spec_summary_for_field", "spec_summary_for_stage",
    "spec_summary_for_subfield",
]
