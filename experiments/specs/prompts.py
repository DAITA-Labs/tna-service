"""Judge prompt TEMPLATES — built from spec data.

Each prompt is a Python f-string with named placeholders. Rendering is done
in render.py — the renderer pulls spec data (patterns/anti-patterns/examples
etc.) and fills the template. Update a spec → next render uses the new data.

To add a new judge:
  1. Add JudgeType enum value in enums.py
  2. Add prompt template here
  3. Add input/output Pydantic schemas in schemas.py
  4. Add renderer function in render.py
"""
from __future__ import annotations


# =============================================================================
# Per-finding judge — fires on ONE finding at a time
# =============================================================================

FIELD_FINDING_JUDGE_PROMPT = """\
# Your role

You are reviewing ONE field match found by a deterministic extractor in a
TNA (Time and Action) spreadsheet. The extractor identified a label cell
(holding a field's name like "IO No") next to a value cell (holding the
field's value like "1063") and decided this maps to a particular field.

Your job is to issue a VERDICT confirming or rejecting that decision. You
do NOT need to extract anything — the extraction is done. You review.

# Key terms

- CANONICAL: a well-known field name in our system. We have a closed set
  of 9 identifier canonicals: io_number, quantity, style_code, style_name,
  color_code, color_name, fabric_code, fabric_name, delivery_date.
  Each canonical has a SPEC describing what it looks like.
- SPEC: rules describing a canonical — its description, label patterns,
  anti-patterns (what to NOT match), value dtype, real-world examples.
- The field shown below is the canonical the deterministic extractor THINKS
  this label maps to. Your job is to confirm.

# Field under review

Canonical:   {canonical}
Description: {description}
Mandatory:   {mandatory}     (every PLI must have this field)

POSITIVE patterns — labels that LOOK LIKE this canonical:
{patterns_bullets}

ANTI-patterns — labels that LOOK SIMILAR but are something else:
{anti_patterns_bullets}

Real example labels seen in our dataset for this canonical:
{examples_bullets}

# The deterministic match to review

Pattern used:    {pattern_used}
Label cell:      {label_cell}  (text="{label_text}")
Value cell:      {value_cell}  (value="{value}", observed dtype={value_dtype_observed})
Confidence:      {confidence}  (deterministic extractor's confidence; 1.0 = certain)

Evidence the extractor used:
{evidence_bullets}

# Other canonicals this label COULD match (competing candidates)

{competing_bullets}

# Sheet sample (cells around the match — for visual context)

{sheet_sample_block}

# Your verdict (STRUCTURED JSON ONLY — no prose outside the braces)

{{
  "verdict":    "yes" | "no" | "swap" | "refine_spec" | "needs_more_context",
  "reason":    "<one short sentence, max 200 chars>",
  "target":    "<canonical name>",
  "confidence": <float 0.0..1.0>
}}

Verdict meanings (specific to THIS prompt):
  yes                — the match is correct; the label cell does mean this
                       canonical, and the value cell holds its value.
  no                 — the match is wrong; this label does NOT mean this
                       canonical. The finding will be dropped.
  swap               — the LABEL is right but the CANONICAL the extractor
                       chose is wrong. The label actually means a different
                       canonical. Put the correct canonical in `target`.
                       (Example: extractor said io_number but the label
                        actually means buyer_po_no.)
  refine_spec        — the match is correct, but the alias/pattern the
                       extractor used was weak. The spec for this canonical
                       should add a stronger pattern. Verdict still counts
                       as a "yes" for this finding; the refinement is for
                       offline spec improvement.
  needs_more_context — you cannot decide alone. The arbiter judge that sees
                       all findings together will resolve it.
"""


# =============================================================================
# Phase identifier judge — fires AFTER per-finding judges, on the WHOLE set
# =============================================================================

PHASE_IDENTIFIER_JUDGE_PROMPT = """\
You are the ARBITER for the identifier-extraction phase. Per-finding judges
have reviewed individual matches and produced recommendations. Your job is
to look at the FULL set and decide what the final findings should be.

You have three actions available:
  - ACCEPT     → ship these findings as-is
  - RE_EXTRACT → re-run the deterministic pass with refinement hints
                  (e.g. exclude_cells, extend_alias). Bounded to 2 iterations.
  - ESCALATE   → ship with warnings; needs human review

# Sheet context

pli_mode:    {pli_mode}
iteration:   {iteration} of {max_iterations}
shape_brief: {shape_brief}

# Mandatory identifier fields (must be present in final findings)

{mandatory_list}

# Findings + per-finding judgments

{findings_with_judgments_block}

# Reasoning checklist (review in this order)

1. Cross-cell conflicts: any two findings claiming the same cell with
   different canonicals? (e.g. color_code + color_name on H4). Resolve.
2. Mandatory gap: any mandatory canonical missing? If yes, can RE_EXTRACT
   with refinement hints recover it (e.g. extend an alias)? If no, ESCALATE.
3. "Swap" recommendations from per-finding judges: apply or reject each.
4. "No" recommendations: drop those findings, log warning.
5. Anything still ambiguous: ESCALATE with a clear warning.

# Your decision (STRUCTURED JSON ONLY)

{{
  "action":           "accept" | "re_extract" | "escalate",
  "final_findings":   [
    {{"canonical": "...", "cell": "...", "value": "...",
      "confidence": 0.0..1.0, "judge_action": "approved|swapped_from_X|..."}}
  ],
  "refinement_hints": {{                           // ONLY for "re_extract"
    "exclude_cells":  ["..."],
    "extend_alias":   {{"<canonical>": ["new alias", ...]}},
    "relax_mode":     {{"<canonical>": "soft"}}
  }},
  "warnings":         ["..."],                     // ONLY for "escalate"
  "reason":           "<one short sentence explaining the decision>"
}}
"""


# =============================================================================
# Per-band stage judge — fires per detected stage band
# =============================================================================

STAGE_BAND_JUDGE_PROMPT = """\
# Your role

You are reviewing ONE detected stage band in a TNA (Time and Action)
spreadsheet. A "stage band" is a column-range (or multi-column group)
representing one production stage — for example sewing, cutting, fabric
inhousing, final inspection, bulk packing.

A deterministic detector has identified a candidate band by looking for
columns that contain date-typed values and sit under a header cell with
text. Your job is to confirm or reject this band and verify the name we
read for it.

# Key facts about stages in this system

- A stage's NAME is whatever the supplier WROTE in the header cell. Stage
  names are an OPEN vocabulary — they vary per supplier and per buyer.
  Examples: "Sewing", "SEW", "BULK PACKING", "FUSING", "WEAVING START".
- Each stage has at minimum a NAME and a PLAN_DATE. Other sub-fields
  (actual_date, received_date, remarks) are optional metadata.
- We maintain a small HINT TABLE of common stage names. Matching the hint
  table is OPTIONAL — a stage with a name not in the table is still a
  valid stage and ships verbatim.

# What you need to decide

  1. Is the candidate band actually a STAGE? (vs. a per-PLI delivery_date
     column, an order_receipt_date column, or a metadata block.)
  2. Is the name text we read CORRECT? (Merged-cell layouts can cause the
     detector to pick the wrong row's text.)

You do NOT need to map the name to a canonical. The detector will attempt
that automatically against the hint table; if no match, the stage simply
ships with the name verbatim.

# Detected band

Band index:        {band_index}
Column range:      {column_range}
Header text read:  "{candidate_stage}"
All cells in band's header row: {name_row_text}
Plan-date sub-column: {plan_date_col}
Detector confidence: {confidence}

Evidence the detector used:
{evidence_bullets}

# Sheet sample (rows around this band)

{sheet_sample_block}

# Closest matches in the known-stage hint table (advisory; not exhaustive)

{candidates_block}

# Cases that look like stages but are NOT

- Per-PLI delivery_date column — has dates but is one of the 9 identifier
  fields, not a stage. Usually labeled "Delivery", "ETA", "ETD", "Ship Date".
- order_receipt_date — sheet-level metadata, not a stage.
- A "Fabric #" / "Fabric Code" column — that's an identifier column with
  alphanumeric codes (no dates), not the fabric stage.

# Cases that ARE stages even if unfamiliar

- Bands with names like "BULK PACKING", "FUSING", "WEAVING START" — these
  are valid stages. Return "yes". Their canonical will simply be null.

# Your verdict (STRUCTURED JSON ONLY — no prose outside the braces)

{{
  "verdict":    "yes" | "no" | "swap" | "needs_more_context",
  "reason":    "<one short sentence explaining the verdict>",
  "target":    "<corrected verbatim name text>",
  "confidence": <float 0.0..1.0>
}}

Verdict meanings (specific to THIS prompt):
  yes                — the band is a stage AND the name we read is correct
  no                 — this is not a stage at all (it's an identifier column,
                       a metadata block, or otherwise misclassified)
  swap               — it IS a stage, but the name text we read is wrong.
                       Provide the correct verbatim text in `target`.
                       (Example: detector read sub-row "PLAN" but the actual
                        stage name in the row above is "SEWING".)
  needs_more_context — you cannot decide alone; will escalate to the
                       arbiter judge that sees all bands together.
"""


# =============================================================================
# Phase stage judge — arbitrates across all detected bands
# =============================================================================

PHASE_STAGE_JUDGE_PROMPT = """\
You are the ARBITER for the stage-detection phase. OPEN VOCABULARY: stages
keep their supplier-written `name` verbatim. `canonical` is only set when
the name matched our known-stage hint table; it is OPTIONAL and may be null
for any stage. New TNAs WILL have novel stage names — that is expected.

# Sheet context

pli_mode:        {pli_mode}
arena_bounds:    {arena_bounds}
iteration:       {iteration} of {max_iterations}

# Detected bands + per-band judgments

{bands_with_judgments_block}

# Reasoning checklist

1. Overlapping bands: any two bands sharing columns? Pick one or split.
2. Plausible chronology: do the bands appear in a sensible order along the
   columns? (Stages on TNAs usually run left-to-right in chronological
   order.) Out-of-order bands are a warning sign, not an automatic reject.
3. Missing critical stages: every TNA should have at least one production
   stage. Zero stages on a sheet that's clearly ROW_PER_PLI is suspicious.
4. Apply per-band judgments (yes/no/swap of raw name).
5. If still uncertain: RE_EXTRACT with hints OR ESCALATE.

# Stage shape contract (MUST match — every entry of final_stages)

OPEN VOCABULARY: `name` = supplier's text verbatim. `canonical` = optional.
ONLY `name` and `plan_date` are first-class. EVERY other sub-column captured
by the deterministic layer (actual_date, approval_date, received_date,
remarks, qty, etc.) goes into `stage_metadata` as a k:v entry. Unknown
sub-columns also go into stage_metadata under their raw label.

# Your decision (STRUCTURED JSON ONLY)

{{
  "action":           "accept" | "re_extract" | "escalate",
  "final_stages":     [
    {{
      "name":           "<supplier's stage text VERBATIM, e.g. 'SEWING' or 'BULK PACKING'>",
      "canonical":      "<known canonical or null>",
      "plan_date":      "<ISO date or null>",
      "plan_date_col":  <int or null>,
      "column_range":   [<start_col>, <end_col>],
      "stage_metadata": {{
        "actual_date":   "<date or null>",
        "received_date": "<date or null>",
        "remarks":       "<text>",
        "<raw_label>":   "<value>"      // unknown sub-cols allowed
      }},
      "judge_action":   "approved|name_corrected|added_by_phase_judge|..."
    }}
  ],
  "refinement_hints": {{...}},
  "warnings":         ["..."],
  "reason":           "<short>"
}}
"""


# =============================================================================
# Metadata judges
# =============================================================================

METADATA_KV_JUDGE_PROMPT = """\
# Your role

You are reviewing ONE metadata key-value pair extracted from a TNA
spreadsheet. Metadata is sheet-level (or group-level) information that
is NOT one of the 9 identifier fields (io_number / quantity / style_code
/ style_name / color_code / color_name / fabric_code / fabric_name /
delivery_date) and NOT a stage.

# Key facts

- Metadata uses an OPEN schema. The label's text is captured VERBATIM as
  the entry's `key`. A `canonical` name (from the hint table below) is
  OPTIONAL — many novel labels will ship with `canonical=null`, and that
  is correct behaviour.
- Examples of metadata: buyer name, season, factory, buyer PO number,
  order receipt date, ex-factory date, treatment, country of origin,
  test-request notes, special instructions.
- If the candidate is actually one of the 9 identifiers or a stage (the
  deterministic layer mis-routed), return "no".

# KV under review

Label cell:  {label_cell}  (text="{label_text}")
Value cell:  {value_cell}  (value="{value}")

# Closest hints from our known-metadata table (advisory; not exhaustive)

{candidates_block}

Evidence the extractor used:
{evidence_bullets}

# Your verdict (STRUCTURED JSON ONLY)

{{
  "verdict":    "yes" | "no" | "swap" | "needs_more_context",
  "reason":    "<one short sentence>",
  "target":    "<known canonical from hint table>",
  "confidence": <float 0.0..1.0>
}}

Verdict meanings (specific to THIS prompt):
  yes                — this IS a metadata k:v pair AND the canonical we
                       chose (or `null` for novel labels) is appropriate
  no                 — this is NOT metadata (e.g. it's actually an
                       identifier value mis-routed; or it's data noise)
  swap               — it IS metadata but a different canonical from our
                       hint table fits better. Provide the canonical in
                       `target`. Use `target=null` if NO hint applies (the
                       entry ships with canonical=null).
  needs_more_context — escalate to the phase judge
"""


PHASE_METADATA_JUDGE_PROMPT = """\
# Your role

You are the ARBITER for the metadata-extraction phase. The deterministic
layer found candidate k:v pairs across the sheet that are NOT identifiers
(the 9 closed-set fields) and NOT stages. Per-kv judges have reviewed
individual entries. You produce the final metadata list.

# Open-schema rules

Metadata uses an OPEN schema. Each final entry is a MetadataEntry with:
  - `key`        : the raw label text from the sheet, VERBATIM
  - `value`      : the value cell contents
  - `source`     : cell reference where the value was read
  - `canonical`  : OPTIONAL — set ONLY when the raw label matched one of
                   the known-canonical hints (e.g. "Buyer" → buyer). For
                   novel labels (Buyer Po No, Treatment, Country, etc.)
                   leave canonical=null. That is correct behaviour.
  - `scope`      : "sheet" (broadcast to all PLIs), "group" (subset of
                   PLIs), or "pli" (per-PLI). Most metadata is "sheet".

# Detected k:v pairs + per-kv judgments

{kvs_with_judgments_block}

# Reasoning checklist

1. Drop entries with "no" verdict (not actually metadata — likely data noise).
2. Apply "swap" verdicts (use the target canonical, or null if the judge
   said no hint fits).
3. Unknown labels (no spec match, judge said "yes") — keep them with
   `canonical=null` and `key=<raw label>`. NEW LABELS ARE EXPECTED.
4. Conflicts (two entries with the same key+source) — pick the higher-confidence one.
5. If a key is missing that the sheet clearly has (e.g. an obvious "Buyer:"
   label was skipped), choose RE_EXTRACT with a hint to widen the scan.

# Your decision (STRUCTURED JSON ONLY)

{{
  "action":           "accept" | "re_extract" | "escalate",
  "final_metadata":   [
    {{
      "key":       "<raw label text verbatim>",
      "value":     "<value>",
      "source":    "<cell ref>",
      "canonical": "<known canonical>" or null,
      "scope":     "sheet" | "group" | "pli",
      "group_id":  "<group id>" or null,
      "confidence": <float 0.0..1.0>
    }},
    ...
  ],
  "refinement_hints": {{...}},
  "warnings":         ["..."],
  "reason":           "<one short sentence>"
}}
"""


# =============================================================================
# Classification judge — only fires on TIED votes
# =============================================================================

CLASSIFICATION_JUDGE_PROMPT = """\
You are the tiebreaker for sheet classification. The deterministic
multi-check voting could not produce a clear winner. Pick the pli_mode.

# Shape brief

{shape_brief}

# Vote breakdown (each pli_mode and its weighted score)

{vote_breakdown_block}

# Evidence per check (what each check observed)

{evidence_per_check_block}

# Three modes — when to pick each

- ROW_PER_PLI:     tall data rectangle, header row with stage columns,
                   one PLI per row of data
- SHEET_IS_PLI:    scattered label-value pairs, one PLI described in metadata
                   blocks across the sheet
- SECTION_PER_PLI: multiple distinct blocks separated by blank rows or
                   repeating labels; each block is one PLI

# Your decision (STRUCTURED JSON ONLY)

{{
  "chosen_mode": "row_per_pli" | "sheet_is_pli" | "section_per_pli",
  "confidence":  0.0..1.0,
  "reason":      "<one short sentence>"
}}
"""
