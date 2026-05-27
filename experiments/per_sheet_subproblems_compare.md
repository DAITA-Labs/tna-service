# Per-sheet sub-problem deterministic strategy comparison

## 1. Overview

Compared 2-3 deterministic strategies per sub-problem against a corpus derived from `dataset/extracted/*.json` (labels), `dataset/*.xlsx` (raw headers), and the eval run `evals/runs/20260520T114423Z/outputs/*.json` (canonical -> cell address crosswalk). For label-mapping problems we deduped to unique (raw, canonical, file) triples; for structural-detection problems we built one (sheet -> expected) case per workbook. Eval-output crosswalks were filtered with a plausibility check (raw shares at least one token with the canonical, or the alias table maps it directly) to keep model-error mappings out of the ground truth.

## 2. Sub-problem #6 — identity-field label mapping

### Corpus stats

- Total pairs: 189
- Unique canonicals: 20
- Files contributing: 18
- Source breakdown: {'eval_output': 189}
- Top canonicals: `quantity` (20), `style_code` (18), `fabric_code` (15), `io_number` (15), `style_name` (13), `color_name` (13), `season` (12), `delivery_date` (11)

### Per-strategy scores

| Strategy | Precision | Recall | F1 | Answered/Total |
| --- | --- | --- | --- | --- |
| vocab | 94.8% | 88.7% | 91.7% | 174/186 |
| fuzzy | 90.2% | 89.2% | 89.7% | 184/186 |
| jaccard | 89.6% | 83.3% | 86.4% | 173/186 |
| sample_value | 23.3% | 16.1% | 19.0% | 129/186 |
| combined | 89.2% | 89.2% | 89.2% | 186/186 |

### Hardest cases


**vocab** — top 5 errors:
- `'Color'` -> got `color_name`, expected `color_code` (score=1.0)
- `'Col'` -> got `(no match)`, expected `quantity` (score=0.0)
- `'Style Name'` -> got `style_name`, expected `style_code` (score=1.0)
- `'Planned'` -> got `(no match)`, expected `pps_completion` (score=0.0)
- `'PO NO'` -> got `io_number`, expected `buyer_po_no` (score=1.0)
- top confusion pairs (expected -> predicted):
  - `color_code` mis-mapped to `color_name` (5x)
  - `buyer_po_no` mis-mapped to `io_number` (3x)
  - `style_code` mis-mapped to `style_name` (1x)

**fuzzy** — top 5 errors:
- `'Color'` -> got `color_name`, expected `color_code` (score=1.0)
- `'Col'` -> got `color_code`, expected `quantity` (score=0.9)
- `'Style Name'` -> got `style_name`, expected `style_code` (score=1.0)
- `'Planned'` -> got `(no match)`, expected `pps_completion` (score=0.72)
- `'PO NO'` -> got `io_number`, expected `buyer_po_no` (score=1.0)
- top confusion pairs (expected -> predicted):
  - `quantity` mis-mapped to `color_code` (9x)
  - `color_code` mis-mapped to `color_name` (5x)
  - `buyer_po_no` mis-mapped to `io_number` (3x)

**jaccard** — top 5 errors:
- `'Buyer'` -> got `io_number`, expected `buyer` (score=1.0)
- `'Color'` -> got `color_name`, expected `color_code` (score=1.0)
- `'Col'` -> got `(no match)`, expected `quantity` (score=0.0)
- `'Style Name'` -> got `style_name`, expected `style_code` (score=1.0)
- `'Planned'` -> got `(no match)`, expected `pps_completion` (score=0.0)
- top confusion pairs (expected -> predicted):
  - `buyer` mis-mapped to `io_number` (9x)
  - `color_code` mis-mapped to `color_name` (5x)
  - `buyer_po_no` mis-mapped to `io_number` (3x)

**sample_value** — top 5 errors:
- `'Buyer'` -> got `style_name`, expected `buyer` (score=0.6)
- `'Factory'` -> got `(no match)`, expected `factory` (score=0.0)
- `'CT Season'` -> got `(no match)`, expected `season` (score=0.0)
- `'Style No'` -> got `(no match)`, expected `style_code` (score=0.0)
- `'Fabric Quality'` -> got `style_name`, expected `fabric_code` (score=0.6)
- top confusion pairs (expected -> predicted):
  - `fabric_code` mis-mapped to `style_name` (14x)
  - `buyer` mis-mapped to `style_name` (9x)
  - `order_receipt_date` mis-mapped to `delivery_date` (9x)

**combined** — top 5 errors:
- `'Color'` -> got `color_name`, expected `color_code` (score=1.0)
- `'Col'` -> got `color_code`, expected `quantity` (score=0.9)
- `'Style Name'` -> got `style_name`, expected `style_code` (score=1.0)
- `'Planned'` -> got `delivery_date`, expected `pps_completion` (score=1.0)
- `'PO NO'` -> got `io_number`, expected `buyer_po_no` (score=1.0)
- top confusion pairs (expected -> predicted):
  - `quantity` mis-mapped to `color_code` (9x)
  - `color_code` mis-mapped to `color_name` (5x)
  - `buyer_po_no` mis-mapped to `io_number` (3x)

### Ranking

1. **vocab** (F1=91.7%)
2. **fuzzy** (F1=89.7%)
3. **combined** (F1=89.2%)
4. **jaccard** (F1=86.4%)
5. **sample_value** (F1=19.0%)

### Recommendation

Ship deterministic with LLM judge fallback. Best strategy `vocab` reaches F1 91.7%; the 21 unhandled inputs need either vocab expansion or a low-cost judge call when the strategy returns score < threshold.

## 3. Sub-problem #9 — stage-name mapping

### Corpus stats

- Total pairs: 256
- Unique canonicals: 21
- Files contributing: 23
- Source breakdown: {'eval_output': 114, 'labels_json': 142}
- Top canonicals: `final_inspection` (30), `sewing_start` (23), `fit_send` (20), `cutting` (19), `sewing` (19), `in_house_fabric_send` (18), `pre_production_send` (18), `fit_approval` (16)

### Per-strategy scores

| Strategy | Precision | Recall | F1 | Answered/Total |
| --- | --- | --- | --- | --- |
| vocab | 98.2% | 88.0% | 92.8% | 171/191 |
| fuzzy | 91.0% | 90.1% | 90.5% | 189/191 |
| jaccard | 94.9% | 88.0% | 91.3% | 177/191 |
| combined | 91.0% | 90.1% | 90.5% | 189/191 |

### Hardest cases


**vocab** — top 5 errors:
- `'FABRIC IN-HOUSED ON'` -> got `in_house_fabric_approval`, expected `in_house_fabric_send` (score=1.0)
- `'FABRIC ETA PLAN'` -> got `in_house_fabric_send`, expected `fabric` (score=1.0)
- `'START'` -> got `(no match)`, expected `sewing_start` (score=0.0)
- `'END'` -> got `(no match)`, expected `sewing_end` (score=0.0)
- `'PP Sent'` -> got `(no match)`, expected `pre_production_send` (score=0.0)
- top confusion pairs (expected -> predicted):
  - `in_house_fabric_send` mis-mapped to `in_house_fabric_approval` (2x)
  - `fabric` mis-mapped to `in_house_fabric_send` (1x)

**fuzzy** — top 5 errors:
- `'FABRIC IN-HOUSED ON'` -> got `in_house_fabric_approval`, expected `in_house_fabric_send` (score=1.0)
- `'FABRIC ETA PLAN'` -> got `in_house_fabric_send`, expected `fabric` (score=1.0)
- `'START'` -> got `garment_pattern`, expected `sewing_start` (score=0.9)
- `'END'` -> got `lab_dip_send`, expected `sewing_end` (score=0.9)
- `'Print/stone Send Plan'` -> got `printing`, expected `art_work_send` (score=0.9)
- top confusion pairs (expected -> predicted):
  - `in_house_fabric_send` mis-mapped to `in_house_fabric_approval` (2x)
  - `sewing_start` mis-mapped to `garment_pattern` (2x)
  - `sewing_end` mis-mapped to `lab_dip_send` (2x)

**jaccard** — top 5 errors:
- `'FABRIC IN-HOUSED ON'` -> got `in_house_fabric_approval`, expected `in_house_fabric_send` (score=1.0)
- `'FABRIC ETA PLAN'` -> got `in_house_fabric_send`, expected `fabric` (score=1.0)
- `'START'` -> got `cutting`, expected `sewing_start` (score=0.5)
- `'END'` -> got `cutting`, expected `sewing_end` (score=0.5)
- `'PP Sent'` -> got `(no match)`, expected `pre_production_send` (score=0.333)
- top confusion pairs (expected -> predicted):
  - `in_house_fabric_send` mis-mapped to `in_house_fabric_approval` (2x)
  - `sewing_start` mis-mapped to `cutting` (2x)
  - `sewing_end` mis-mapped to `cutting` (2x)

**combined** — top 5 errors:
- `'FABRIC IN-HOUSED ON'` -> got `in_house_fabric_approval`, expected `in_house_fabric_send` (score=1.0)
- `'FABRIC ETA PLAN'` -> got `in_house_fabric_send`, expected `fabric` (score=1.0)
- `'START'` -> got `garment_pattern`, expected `sewing_start` (score=0.9)
- `'END'` -> got `lab_dip_send`, expected `sewing_end` (score=0.9)
- `'Print/stone Send Plan'` -> got `printing`, expected `art_work_send` (score=0.9)
- top confusion pairs (expected -> predicted):
  - `in_house_fabric_send` mis-mapped to `in_house_fabric_approval` (2x)
  - `sewing_start` mis-mapped to `garment_pattern` (2x)
  - `sewing_end` mis-mapped to `lab_dip_send` (2x)

### Ranking

1. **vocab** (F1=92.8%)
2. **jaccard** (F1=91.3%)
3. **fuzzy** (F1=90.5%)
4. **combined** (F1=90.5%)

### Recommendation

Ship deterministic with LLM judge fallback. Best strategy `vocab` reaches F1 92.8%; the 23 unhandled inputs need either vocab expansion or a low-cost judge call when the strategy returns score < threshold.

## 4. Sub-problem #10 — sub-field label mapping

### Corpus stats

- Total pairs: 253
- Unique canonicals: 6
- Files contributing: 16
- Source breakdown: {'eval_output': 29, 'xlsx_scan': 224}
- Top canonicals: `planned_date` (123), `actual_date` (80), `quantity` (31), `remarks` (12), `approval_date` (6), `received_date` (1)

### Per-strategy scores

| Strategy | Precision | Recall | F1 | Answered/Total |
| --- | --- | --- | --- | --- |
| vocab | 100.0% | 100.0% | 100.0% | 75/75 |
| fuzzy | 100.0% | 100.0% | 100.0% | 75/75 |
| combined | 100.0% | 100.0% | 100.0% | 75/75 |

### Hardest cases


**vocab** — no errors.

**fuzzy** — no errors.

**combined** — no errors.

### Ranking

1. **vocab** (F1=100.0%)
2. **fuzzy** (F1=100.0%)
3. **combined** (F1=100.0%)

### Recommendation

Ship deterministic-only. Best strategy `vocab` reaches F1 100.0% on this corpus — the residual 0 misses are dominated by tail vocabulary that can be folded into the vocab table over time. No LLM judge needed for #10 sub-field.

## 5. Sub-problem #4 — stage-band detection

### Corpus stats

- Total files: 24
- Files with detectable ground truth (≥1 expected stage column): 18
- Files with no expected stages: 6 (63261-TNA - Copy, 63261-TNA, NEW, TNA DETAILS, new Eastman TnAs)

### Per-strategy scores

| Strategy | Macro Precision | Macro Recall | Macro F1 | Files |
| --- | --- | --- | --- | --- |
| date_density | 47.9% | 81.8% | 58.0% | 18 |
| vocab_row | 77.5% | 97.0% | 85.2% | 18 |
| hybrid | 77.5% | 97.0% | 85.2% | 18 |

### Hardest cases


**date_density** — top 5 problem files:
- `20260213 MOPD FW26(1) MA08 MA09 COMPASS PRO` (P=0.412, R=1.0) missed=[] spurious=['AA', 'AC', 'AF', 'O', 'P', 'Q', 'S', 'U', 'W', 'X']
- `20260304 MOPD W26(1) MANOS COMPASS PRO` (P=0.389, R=1.0) missed=[] spurious=['AA', 'AC', 'AF', 'AH', 'O', 'P', 'Q', 'S', 'U', 'W', 'X']
- `20260420 MOP W26(1) 608-609 COMPASS PRO` (P=0.412, R=1.0) missed=[] spurious=['AB', 'AE', 'AG', 'N', 'O', 'P', 'R', 'T', 'W', 'Z']
- `20260420 MOP W26(1) CE08-MA08-MA09 COMPASS PRO` (P=0.389, R=1.0) missed=[] spurious=['AB', 'AE', 'AG', 'N', 'O', 'P', 'R', 'T', 'V', 'W', 'Z']
- `20260420 MOP W26(1) MANOS07-08 COMPASS PRO` (P=0.412, R=1.0) missed=[] spurious=['AB', 'AE', 'AG', 'N', 'O', 'P', 'R', 'T', 'W', 'Z']

**vocab_row** — top 2 problem files:
- `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #2` (P=0.917, R=0.733) missed=['AH', 'AI', 'AR', 'AS'] spurious=['AB']
- `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #3` (P=0.917, R=0.733) missed=['AH', 'AI', 'AR', 'AS'] spurious=['AB']

**hybrid** — top 2 problem files:
- `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #2` (P=0.917, R=0.733) missed=['AH', 'AI', 'AR', 'AS'] spurious=['AB']
- `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #3` (P=0.917, R=0.733) missed=['AH', 'AI', 'AR', 'AS'] spurious=['AB']

### Ranking

1. **vocab_row** (F1=85.2%)
2. **hybrid** (F1=85.2%)
3. **date_density** (F1=58.0%)

### Recommendation

Ship `vocab_row` deterministic-only for #4 band detection. Macro F1 85.2% across 18 files.

## 6. Sub-problem #5 — sub-column detection

### Corpus stats

- Total files: 24
- Files with detectable sub-column row: 14
- Files with no sub-column row (single-row layout / no vocab hits): 10
- Avg expected sub-cols per file (where present): 14.7

### Per-strategy scores

| Strategy | Macro Precision | Macro Recall | Macro F1 | Files |
| --- | --- | --- | --- | --- |
| single_row | 92.9% | 92.9% | 92.9% | 14 |
| multi_row | 92.9% | 92.9% | 92.9% | 14 |
| inferred | 100.0% | 100.0% | 100.0% | 14 |

### Hardest cases


**single_row** — top 1 problem files:
- `FA26 YC & EUROPE T&A #1` (P=0.0, R=0.0) missed=[('AA', 'REMARKS'), ('H', 'QTY')] spurious=[]

**multi_row** — top 1 problem files:
- `FA26 YC & EUROPE T&A #1` (P=0.0, R=0.0) missed=[('AA', 'REMARKS'), ('H', 'QTY')] spurious=[]

**inferred** — no problem files.

### Ranking

1. **inferred** (F1=100.0%)
2. **single_row** (F1=92.9%)
3. **multi_row** (F1=92.9%)

### Recommendation

Ship `inferred` deterministic-only for #5 sub-column. Macro F1 100.0% across 14 files.

## 7. Cross-cutting observations

- identity-field: fuzzy matching's top confusions are `quantity` vs `color_code` (9x), `color_code` vs `color_name` (5x), `buyer_po_no` vs `io_number` (3x) — these canonicals have overlapping aliases and require token-weight tweaks or sample-value disambiguation.
- stage: fuzzy matching's top confusions are `in_house_fabric_send` vs `in_house_fabric_approval` (2x), `sewing_start` vs `garment_pattern` (2x), `sewing_end` vs `lab_dip_send` (2x) — these canonicals have overlapping aliases and require token-weight tweaks or sample-value disambiguation.
- band detection: `vocab_row` outperforms the other approach by 27.2pp — the layouts in our corpus respond more to header vocabulary.

## 7a. Caveats

- **#10 (sub-field) F1 100% is also partially tautological** for the `xlsx_scan` slice of the corpus: those 224 pairs were derived by scanning xlsx cells whose normalised text matched the same alias table the vocab strategy uses. The 29 `eval_output` pairs are an independent signal; the strategies still score 100% on them too. Take #10 = 100% to mean 'no sub-field label in the corpus is outside the alias table', not 'the strategy is infallible'. A new file with a novel sub-label vocabulary (e.g. 'Delivered', 'Pending') would not match. Risk is low because the sub-field canonical set is small (~9) and tail vocab grows slowly.
- **#5 (sub-column) `inferred` strategy** scores 100% because it picks the row with the most sub-field-vocab matches — which is the exact heuristic used to derive the ground-truth. The 100% is a tautology; treat it as the upper bound a vocab-driven detector can reach. `single_row` and `multi_row` start from a fixed `stage_name_row + 1` and are the more honest comparison: their F1 of 92.9% reflects real failures on FA26-style sheets where the stage band and sub-column labels are interleaved on the same row.
- **#6 hardest cases** include genuinely ambiguous labels: `'Color'` is `color_code` on DKN sheets (4-digit values like '6602') and `color_name` on CHRISTIAN BERG ('422 - MAGENTA'). Static vocab cannot disambiguate these without looking at sample values; sample_value alone is too coarse (one canonical per dtype). A value-aware secondary signal (combined strategy) gains 2pp over vocab on dtype-overloaded canonicals but loses on text-pattern fields where dtype is the same across canonicals (style_name vs fabric_code vs buyer — all long strings).
- **Eval-output noise in stage_pairs**: the labels-side ground truth and the live extracted output disagree on which sub-column is the canonical 'planned_date'. The plausibility filter removes obvious nonsense (`Delivery date -> lab_dip_approval`), but some pairs are still derived from the model's interpretation rather than the labeller's. Treat #9 F1 as a directional ceiling, not an absolute one.
- **#4 GUESS files** are the strongest signal that vocab needs iterative expansion: 'PROGRAM SUBMIT ON', 'FABRIC ETA PLAN', 'FABRIC IN-HOUSED ON' were unmappable until we added them to the alias table. Each new TNA family will surface a new tail. This argues for a judge fallback that proposes vocab additions, not for replacing vocab with a smarter algorithm.

## 7b. Direct answers to the calling questions

**Q1 — Is a static vocab table enough for #6/#9/#10?**
- **#10 (sub-field)**: yes. Vocab reaches F1 100.0% with 6 canonicals and ~30 aliases. Tail risk: novel sub-labels (e.g. 'Delivered', 'Pending') would fall through.
- **#9 (stage-name)**: mostly. Vocab F1 92.8%. Failures: bare `'START'` / `'END'` headers (no context — these sit alongside columns named 'SEWING' so context is a sibling column), and `EMB RECVD Plan` / `EMB Send Plan` (variant of art_work_*; can be added to alias table). `FABRIC IN-HOUSED ON` is structurally ambiguous (send vs approval) and benefits from looking at the date relative to the order receipt date.
- **#6 (identity-field)**: mostly. Vocab F1 91.7%. Failures: `'Color'` (color_code vs color_name — depends on whether values are short codes or descriptive names), `'PO NO'` (io_number vs buyer_po_no — same dtype, no value disambiguation possible), `'Style Name'` (sometimes the style_code column has this header). These need a value-aware secondary signal or a judge call.

**Q2 — Does date-density alone find MOP/MOPD's stages, or do those files genuinely lack signal?**
- MOP/MOPD files have real stage signal. Date-density catches 100% recall on every MOP/MOPD file in the corpus (every expected stage column has dates). The problem is precision: it also picks up identity date columns (`order_receipt_date`, `delivery_date`, the merged `Cut Qty`/`Sewn Qty` columns) and the planned/actual sub-columns. Macro recall for date_density across all files: 81.8%. So the data is there — the strategy needs structural filtering (e.g. exclude columns that have an identity-vocab header, exclude columns under a sub-label-only band).

**Q3 — Can we automate picking the right header row for CHRISTIAN BERG-style sheets?**
- Yes. CHRISTIAN BERG has stage names in row 2 and sub-labels ('PLAN', 'ACT', 'RECVD', 'START PLAN', 'END PLAN') in row 3. The `single_row` strategy (probe row N+1 from stage-name row) handles it perfectly. Macro F1 across all sheets with sub-columns: 92.9%. The only failure is FA26 where stage names AND sub-labels sit on the same row (no sub-band layout) — but that's a different problem class (determining 'is this sheet wide_sub_columns or single_row_only?'), not a sub-column-detection failure per se.


## 8. Recommendation for next steps

Ranking by best honest deterministic F1 (highest first; tautological metrics excluded):
- #10 sub-field: 100.0%
- #5 sub-col detect: 92.9%
- #9 stage-name: 92.8%
- #6 identity-field: 91.7%
- #4 band detect: 85.2%

**Ship-first picks** (highest ROI):
1. **#10 sub-field label mapping** — F1 100% with a tiny vocab table (6 canonicals, ~25 aliases). Lowest-risk, smallest surface, most reusable. Ship as `match_subfield_label(raw) -> MatchResult` with no judge needed.
2. **#9 stage-name mapping** — F1 92.8% with vocab. The remaining errors (`FABRIC IN-HOUSED ON` ambiguity, bare `'START'`/`'END'` headers from CHRISTIAN BERG-style sheets, `EMB RECVD Plan`) are all corpus-specific tail vocabulary. Ship as `match_stage_name(raw) -> MatchResult`; route low-score results to a judge that proposes new aliases instead of mapping ad-hoc.

**Defer**:
- **#6 identity-field** (F1 91.7%) — has genuine ambiguity (`Color` = color_code vs color_name depending on the sheet). Needs value-aware judge fallback, not just vocab. Useful to ship once the value-pattern classifier improves.
- **#4 band detection** (F1 85.2%) — `vocab_row` catches most stages (recall 97%), but precision is dragged down by spurious matches (data-row strings containing 'fabric'). Needs a structural disambiguator (date-density on data rows filters out identity columns). The MOP/MOPD files do have real stage signal (vocab catches every expected column); date-density alone fails on them because most date columns are valid stages — date-density over-collects but doesn't miss.
- **#5 sub-column detection** (`single_row` F1 93%, ignore `inferred`'s 100%) — already mostly works with the row-below heuristic; FA26 is the only real failure and needs a row-disambiguator (which is what the current production code already tries to do).
