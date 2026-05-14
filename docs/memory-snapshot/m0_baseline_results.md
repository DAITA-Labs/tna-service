---
name: M0 baseline results (2026-05-09) — single-prompt control numbers
description: Real Anthropic API numbers from the single-prompt baseline on the DKN labeled file; the floor that the multi-agent system must beat
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
The M0 single-prompt baseline ran live against `dataset\20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx` (DKN columnar, 3 PLIs, 6 stages each) using `claude-sonnet-4-6`. **Two runs to date** — initial M0 prompt vs faithful-extraction prompt (2026-05-09).

| metric | v1 (initial) | v2 (faithful) | meaning |
|---|---|---|---|
| `pli_recall` | 1.000 | **1.000** | 3/3 PLIs found |
| `field_precision` | 0.714 | **1.000** | All canonical PLI fields exact |
| `field_recall` | 0.714 | **1.000** | All canonical PLI fields exact |
| `stage_recall` | 0.833 | **0.833** | 5/6 stages matched per PLI |

**v2 fixed the field-splitting issue** by enforcing faithful-extraction in the prompt. Stage recall held flat — see `faithful_extraction_principle.md` for why (Stage canonicalization remains hard for single-prompt; needs the dedicated Stage Locator agent).

**Failure modes observed:**

1. (v1 only — fixed in v2) The model split `style_code` at the first numeric token and concatenated the rest into `style_name`. Cross-PLI copy errors. **Faithful-extraction prompt fixed both.**
2. (v1 + v2) **Stage canonicalization miss**: the model still emits "Sewing Start" / "Sewing End" as two stages instead of the label's single "Sewing". The "Sewing Start" date is correct (2026-05-23 matches expected); only the name needs canonicalization. **This persists despite explicit prompt instructions.** It's the failure mode a dedicated Stage Locator agent in the multi-agent plan is designed to fix.
3. Per-call latency: ~28-30 s for parse, ~34 s for eval.

**Why this matters:** these are precisely the kinds of errors the multi-agent architecture (Field Locator with concatenation patterns, Stage Locator with multi-band awareness, dedicated PLI Boundary Finder) was designed to fix. The baseline's per-PLI 71.4% accuracy is the number to beat in the follow-up plan.

**How to apply:**
- Output fixture: `F:\DAITA\ARENA\TNA\tna_parser\fixtures\dkn-baseline-output.json` (11 KB, runnable through the eval harness anytime)
- Session log: `F:\DAITA\ARENA\TNA\TNA AI parser\04-sessions\2026-05-09-m0-baseline-results.md`
- Re-run anytime with: `.\.venv\Scripts\python.exe -m tna_parser.cli eval "dataset\20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx" --label "dataset\extracted\20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.json"`
- Run on other labeled files (Compass Pro, GUESS) to widen the picture before the multi-agent plan begins.

**Two fixes the implementer made during Task 12 (both reasonable, both tested):**
1. `anthropic_client.from_env`: now searches upward from `__file__` for `.env` so the lookup works regardless of cwd. Previous `find_dotenv()`-based search was failing when run from project root.
2. `baseline.SYSTEM_PROMPT`: the original "include a confidence in [0,1] for every field" instruction caused the model to wrap each field as `{value, confidence}` objects, conflicting with the flat-value tool schema. Now the prompt redirects per-field confidence into the PLI's `confidence` dict instead. 24 Pydantic validation errors → 0 after the fix.
