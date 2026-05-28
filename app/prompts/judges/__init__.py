"""Judge agent prompts — re-exports for `from app.prompts.judges import ...`."""
from app.prompts.judges.identifier_finding import IDENTIFIER_FINDING_JUDGE
from app.prompts.judges.identifier_phase import IDENTIFIER_PHASE_JUDGE
from app.prompts.judges.metadata import METADATA_FINDING_JUDGE
from app.prompts.judges.stage_finding import STAGE_FINDING_JUDGE
from app.prompts.judges.stage_phase import STAGE_PHASE_JUDGE

__all__ = [
    "IDENTIFIER_FINDING_JUDGE",
    "IDENTIFIER_PHASE_JUDGE",
    "METADATA_FINDING_JUDGE",
    "STAGE_FINDING_JUDGE",
    "STAGE_PHASE_JUDGE",
]
