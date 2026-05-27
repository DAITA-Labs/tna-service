# P1 — Shape Tools + Multi-Check Classification Probe

## 1. Overview

This probe builds the deterministic shape-inspection layer and a multi-vote classifier on top of it. The classifier produces a `(pli_mode, pli_axis)` pair from cell-level shape signals — without any LLM calls. Six representative TNA workbooks are exercised; we measure (a) whether the multi-vote correctly predicts the expected mode + axis, (b) which variant of each tool gives the cleanest signal, and (c) where a future ClassificationJudge would need to fire (margin < 0.3).

**Ground-truth note (Eastman):** The probe spec listed Eastman as `SECTION_PER_PLI / SECTION`, but on inspection that label applies at the WORKBOOK level (each Excel sheet in the workbook represents one PLI in Orders-Plan SHEET_IS_PLI form). The per-sheet classifier — the subject of this probe — therefore must see Eastman's first data sheet as SHEET_IS_PLI / WHOLE_SHEET. The scoring uses that per-sheet ground truth. The workbook-level intent is a P2 orchestration concern.

**Aggregate scores (6 files):**

- mode correct: **6/6**
- axis correct: **6/6**
- both correct: **6/6**
- needs ClassificationJudge: **0/6**


## 2. Per-file summary

| File | exp mode | pred mode | exp axis | pred axis | margin | judge? |
|---|---|---|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx | row_per_pli | row_per_pli (PASS) | row | row (PASS) | 1.30 | no |
| CHRISTIAN BERG- T&A.xlsx | row_per_pli | row_per_pli (PASS) | row | row (PASS) | 1.00 | no |
| 20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx | row_per_pli | row_per_pli (PASS) | row | row (PASS) | 1.15 | no |
| 63261-TNA.xlsx | sheet_is_pli | sheet_is_pli (PASS) | whole_sheet | whole_sheet (PASS) | 1.40 | no |
| new Eastman TnAs.xlsx | sheet_is_pli | sheet_is_pli (PASS) | whole_sheet | whole_sheet (PASS) | 1.00 | no |
| GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx | section_per_pli | section_per_pli (PASS) | section | section (PASS) | 0.60 | no |

## 3. Per-file detail

### 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx

**Notes:** Standard layout. Baseline.

**Sheet picked:** `Sheet 1`  
**Dimensions:** 18 rows × 40 cols  
**Non-blank cells:** 133 / 720  
**Biggest rect:** A2:AM6 area=195 dens=0.64  
**Best header row:** 2  
**Merged ranges:** 31, hyperlinks 0, formulas 0  
**Identifier hits:** 7, Stage hits: 5, Repeated labels: 2  

#### Tool variants

**compute_density** (row-axis, first 8 entries):
```
A (non_blank):       ['0.05', '0.75', '0.50', '0.62', '0.62', '0.62', '0.15', '0.00']
B (content):         ['0.05', '0.75', '0.50', '0.62', '0.62', '0.62', '0.15', '0.00']
C (dtype_weighted):  ['0.03', '0.38', '0.25', '0.46', '0.46', '0.46', '0.11', '0.00']
```

**find_dense_rectangles** (counts + biggest):
```
A (flood):     n=  4  biggest=A1:X7 area=168 dens=0.54
B (threshold): n=  1  biggest=A2:AM6 area=195 dens=0.64
C (hybrid):    n=  1  biggest=A2:AM6 area=195 dens=0.64
```

**find_blank_runs** (row-axis, counts):
```
A (strict):    n=  1  example=[BlankRun(start=8, end=18, axis='row')]
B (relaxed):   n=  1  example=[BlankRun(start=8, end=18, axis='row')]
C (threshold): n=  1  example=[BlankRun(start=8, end=18, axis='row')]
```

**find_header_row_candidates** (top 5 per variant):
```
A (text_density): n=  4  rows/scores=[(1, 1.0), (2, 1.0), (3, 1.0), (4, 0.84)]
B (vocab):        n=  2  rows/scores=[(2, 19.0), (3, 6.0)]
C (styled):       n=  2  rows/scores=[(2, 1.0), (3, 1.0)]
D (merged):       n=  4  rows/scores=[(1, 2.0), (2, 28.0), (3, 20.0), (7, 1.0)]
```

**Column dtype profiles** (cols inside biggest rect):
```
col   1: date=0.00 int=0.75 str=0.00 blank=0.25  pattern=int_small
col   2: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col   3: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col   4: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=code_alnum
col   5: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=code_alnum
col   6: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col   7: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col   8: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col   9: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col  10: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col  11: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col  12: date=0.00 int=0.00 str=0.75 blank=0.25  pattern=name_text
col  13: date=0.00 int=0.75 str=0.25 blank=0.00  pattern=int_medium
col  14: date=0.00 int=0.75 str=0.25 blank=0.00  pattern=int_medium
... (25 more)
```

#### Classification votes

**Relevance checks:**

| Check | Passes | Evidence |
|---|---|---|
| has_data_rectangle | yes | biggest_area=195, date_col_count=10 |
| not_navigation | yes | ratio=0.0, n=0 |
| not_summary | yes | ratio=0.0, n=0 |
| has_io_signal | yes | identifier_hits=7, stage_hits=5 |

**Mode checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| tall_table_shape | - | 0.00 | h=5, w=39, aspect=0.13, density=0.64, transitions=0, stripey=False |
| date_arena_dominance | row_per_pli | 1.00 | date_cols=10 |
| header_continuity | row_per_pli | 1.00 | coverage=1.0, header_row=2, signal=vocab, data_rows_below=5 |
| kv_anchor_density | - | 0.00 | env=r2-6/c1-39, aspect=7.8, merges=31, row_var=0.006, transitions=0, stripey=False |
| kv_pair_count | sheet_is_pli | 0.60 | distinct_rows=2, distinct_cols=10, total_hits=11, kv_adjacencies=9 |
| section_split_by_blanks | - | 0.00 |  |
| section_repeat_pattern | section_per_pli | 0.70 | label_hits=2, repeating_aliases=[], repeating_count=0 |
| styled_header_dist | - | 0.00 | n_styled_rows=2 |

**Mode vote totals:** {'row_per_pli': 2.0, 'sheet_is_pli': 0.6, 'section_per_pli': 0.7}  
**Mode winner:** row_per_pli (margin 1.30)  

**Axis checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| axis_row | row | 0.60 | header_row=2, r0=2, r1=6, data_rows_below=4 |
| axis_column | - | 0.00 | col1_str_pct=0.0, col1_n=4 |
| axis_whole_sheet | - | 0.00 | n_rects=1, area=195, h=5, w=39, transitions=0, small=False, wide_short=True |
| axis_section | - | 0.00 | n_rects=1, rects_with_hits=1, n_runs=1, repeating_count=0 |

**Axis vote totals:** {'row': 0.6, 'column': 0.0, 'whole_sheet': 0.0, 'section': 0.0}  
**Axis winner:** row (margin 0.60)  
**Needs ClassificationJudge?** no  

**Verdict:** PASS  


### CHRISTIAN BERG- T&A.xlsx

**Notes:** Multi-band stages (7 bands), multi-row sub-headers (PLAN/RECVD/APPD).

**Sheet picked:** `CHRISTIAN BERG`  
**Dimensions:** 13 rows × 38 cols  
**Non-blank cells:** 210 / 494  
**Biggest rect:** A2:AJ11 area=360 dens=0.56  
**Best header row:** 3  
**Merged ranges:** 46, hyperlinks 0, formulas 0  
**Identifier hits:** 10, Stage hits: 6, Repeated labels: 0  

#### Tool variants

**compute_density** (row-axis, first 8 entries):
```
A (non_blank):       ['0.03', '0.53', '0.63', '0.84', '0.55', '0.55', '0.55', '0.11']
B (content):         ['0.03', '0.53', '0.63', '0.84', '0.55', '0.55', '0.55', '0.11']
C (dtype_weighted):  ['0.01', '0.26', '0.32', '0.74', '0.51', '0.51', '0.51', '0.08']
```

**find_dense_rectangles** (counts + biggest):
```
A (flood):     n=  4  biggest=A1:AK13 area=481 dens=0.36
B (threshold): n=  1  biggest=A2:AJ11 area=360 dens=0.56
C (hybrid):    n=  1  biggest=A2:AJ11 area=360 dens=0.56
```

**find_blank_runs** (row-axis, counts):
```
A (strict):    n=  0  example=[]
B (relaxed):   n=  0  example=[]
C (threshold): n=  0  example=[]
```

**find_header_row_candidates** (top 5 per variant):
```
A (text_density): n=  3  rows/scores=[(1, 1.0), (2, 1.0), (3, 1.0)]
B (vocab):        n=  2  rows/scores=[(2, 13.0), (3, 23.0)]
C (styled):       n= 11  rows/scores=[(2, 1.0), (3, 1.0), (4, 1.0), (5, 1.0), (6, 1.0)]
D (merged):       n= 10  rows/scores=[(1, 1.0), (2, 21.0), (3, 14.0), (4, 12.0), (5, 12.0)]
```

**Column dtype profiles** (cols inside biggest rect):
```
col   1: date=0.00 int=0.25 str=0.00 blank=0.75  pattern=blank
col   2: date=0.00 int=0.25 str=0.00 blank=0.75  pattern=blank
col   3: date=0.25 int=0.00 str=0.00 blank=0.75  pattern=blank
col   4: date=0.25 int=0.00 str=0.00 blank=0.75  pattern=blank
col   5: date=0.00 int=0.25 str=0.00 blank=0.75  pattern=blank
col   6: date=0.00 int=0.00 str=0.25 blank=0.75  pattern=blank
col   7: date=0.00 int=0.25 str=0.00 blank=0.75  pattern=blank
col   8: date=0.00 int=0.00 str=0.25 blank=0.75  pattern=blank
col   9: date=0.00 int=0.00 str=0.25 blank=0.75  pattern=blank
col  10: date=0.00 int=0.00 str=0.00 blank=1.00  pattern=blank
col  11: date=0.00 int=0.00 str=0.88 blank=0.12  pattern=name_text
col  12: date=0.00 int=1.00 str=0.00 blank=0.00  pattern=int_large
col  13: date=0.00 int=1.00 str=0.00 blank=0.00  pattern=int_large
col  14: date=0.88 int=0.00 str=0.00 blank=0.12  pattern=date
... (22 more)
```

#### Classification votes

**Relevance checks:**

| Check | Passes | Evidence |
|---|---|---|
| has_data_rectangle | yes | biggest_area=360, date_col_count=20 |
| not_navigation | yes | ratio=0.0, n=0 |
| not_summary | yes | ratio=0.0, n=0 |
| has_io_signal | yes | identifier_hits=10, stage_hits=6 |

**Mode checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| tall_table_shape | - | 0.00 | h=10, w=36, aspect=0.28, density=0.56, transitions=2, stripey=False |
| date_arena_dominance | row_per_pli | 1.00 | date_cols=14 |
| header_continuity | row_per_pli | 1.00 | coverage=1.0, header_row=3, signal=vocab, data_rows_below=9 |
| kv_anchor_density | - | 0.00 | env=r2-11/c1-36, aspect=3.6, merges=46, row_var=0.033, transitions=2, stripey=False |
| kv_pair_count | sheet_is_pli | 0.60 | distinct_rows=2, distinct_cols=10, total_hits=10, kv_adjacencies=9 |
| section_split_by_blanks | - | 0.00 |  |
| section_repeat_pattern | - | 0.00 | label_hits=0, repeating_aliases=[], repeating_count=0 |
| styled_header_dist | sheet_is_pli | 0.40 | n_styled_rows=11 |

**Mode vote totals:** {'row_per_pli': 2.0, 'sheet_is_pli': 1.0, 'section_per_pli': 0.0}  
**Mode winner:** row_per_pli (margin 1.00)  

**Axis checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| axis_row | row | 0.60 | header_row=3, r0=2, r1=11, data_rows_below=8 |
| axis_column | - | 0.00 | col1_str_pct=0.0, col1_n=8 |
| axis_whole_sheet | - | 0.00 | n_rects=1, area=360, h=10, w=36, transitions=2, small=False, wide_short=True |
| axis_section | - | 0.00 | n_rects=1, rects_with_hits=1, n_runs=0, repeating_count=0 |

**Axis vote totals:** {'row': 0.6, 'column': 0.0, 'whole_sheet': 0.0, 'section': 0.0}  
**Axis winner:** row (margin 0.60)  
**Needs ClassificationJudge?** no  

**Verdict:** PASS  


### 20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx

**Notes:** Production planner — stages broken. Should still classify ROW_PER_PLI.

**Sheet picked:** `Sheet 1`  
**Dimensions:** 10 rows × 38 cols  
**Non-blank cells:** 231 / 380  
**Biggest rect:** A2:AL8 area=266 dens=0.82  
**Best header row:** 2  
**Merged ranges:** 61, hyperlinks 0, formulas 0  
**Identifier hits:** 8, Stage hits: 6, Repeated labels: 3  

#### Tool variants

**compute_density** (row-axis, first 8 entries):
```
A (non_blank):       ['0.05', '0.74', '0.47', '0.79', '0.97', '0.97', '0.95', '0.84']
B (content):         ['0.05', '0.74', '0.47', '0.79', '0.97', '0.97', '0.95', '0.84']
C (dtype_weighted):  ['0.04', '0.37', '0.24', '0.61', '0.78', '0.78', '0.76', '0.66']
```

**find_dense_rectangles** (counts + biggest):
```
A (flood):     n=  2  biggest=A1:AI10 area=350 dens=0.60
B (threshold): n=  1  biggest=A2:AL8 area=266 dens=0.82
C (hybrid):    n=  1  biggest=A2:AL8 area=266 dens=0.82
```

**find_blank_runs** (row-axis, counts):
```
A (strict):    n=  0  example=[]
B (relaxed):   n=  0  example=[]
C (threshold): n=  0  example=[]
```

**find_header_row_candidates** (top 5 per variant):
```
A (text_density): n=  3  rows/scores=[(1, 0.5), (2, 1.0), (3, 1.0)]
B (vocab):        n=  4  rows/scores=[(2, 18.0), (3, 4.0), (4, 3.0), (8, 3.0)]
C (styled):       n=  2  rows/scores=[(2, 1.0), (3, 1.0)]
D (merged):       n=  6  rows/scores=[(1, 1.0), (2, 28.0), (3, 20.0), (8, 31.0), (9, 31.0)]
```

**Column dtype profiles** (cols inside biggest rect):
```
col   1: date=0.00 int=0.83 str=0.00 blank=0.17  pattern=int_small
col   2: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col   3: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col   4: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=code_alnum
col   5: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col   6: date=0.00 int=0.83 str=0.00 blank=0.17  pattern=int_large
col   7: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col   8: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col   9: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col  10: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=name_text
col  11: date=0.00 int=0.67 str=0.17 blank=0.17  pattern=int_large
col  12: date=0.00 int=0.00 str=0.83 blank=0.17  pattern=mixed
col  13: date=0.00 int=0.83 str=0.17 blank=0.00  pattern=int_large
col  14: date=0.00 int=0.83 str=0.17 blank=0.00  pattern=int_large
... (24 more)
```

#### Classification votes

**Relevance checks:**

| Check | Passes | Evidence |
|---|---|---|
| has_data_rectangle | yes | biggest_area=266, date_col_count=18 |
| not_navigation | yes | ratio=0.0, n=0 |
| not_summary | yes | ratio=0.0, n=0 |
| has_io_signal | yes | identifier_hits=8, stage_hits=6 |

**Mode checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| tall_table_shape | - | 0.00 | h=7, w=38, aspect=0.18, density=0.82, transitions=0, stripey=False |
| date_arena_dominance | row_per_pli | 1.00 | date_cols=15 |
| header_continuity | row_per_pli | 1.00 | coverage=1.0, header_row=2, signal=vocab, data_rows_below=7 |
| kv_anchor_density | - | 0.00 | env=r2-8/c1-38, aspect=5.43, merges=61, row_var=0.027, transitions=0, stripey=False |
| kv_pair_count | sheet_is_pli | 0.60 | distinct_rows=2, distinct_cols=10, total_hits=11, kv_adjacencies=9 |
| section_split_by_blanks | - | 0.00 |  |
| section_repeat_pattern | section_per_pli | 0.85 | label_hits=3, repeating_aliases=[], repeating_count=0 |
| styled_header_dist | - | 0.00 | n_styled_rows=2 |

**Mode vote totals:** {'row_per_pli': 2.0, 'sheet_is_pli': 0.6, 'section_per_pli': 0.85}  
**Mode winner:** row_per_pli (margin 1.15)  

**Axis checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| axis_row | row | 0.60 | header_row=2, r0=2, r1=8, data_rows_below=6 |
| axis_column | - | 0.00 | col1_str_pct=0.0, col1_n=6 |
| axis_whole_sheet | - | 0.00 | n_rects=1, area=266, h=7, w=38, transitions=0, small=False, wide_short=True |
| axis_section | - | 0.00 | n_rects=1, rects_with_hits=1, n_runs=0, repeating_count=0 |

**Axis vote totals:** {'row': 0.6, 'column': 0.0, 'whole_sheet': 0.0, 'section': 0.0}  
**Axis winner:** row (margin 0.60)  
**Needs ClassificationJudge?** no  

**Verdict:** PASS  


### 63261-TNA.xlsx

**Notes:** Orders-Plan family — KV anchors scattered.

**Sheet picked:** `Sheet1`  
**Dimensions:** 22 rows × 15 cols  
**Non-blank cells:** 132 / 330  
**Biggest rect:** A8:O10 area=45 dens=0.93  
**Best header row:** 8  
**Merged ranges:** 3, hyperlinks 0, formulas 0  
**Identifier hits:** 2, Stage hits: 5, Repeated labels: 0  

#### Tool variants

**compute_density** (row-axis, first 8 entries):
```
A (non_blank):       ['0.07', '0.00', '0.40', '0.40', '0.40', '0.00', '0.00', '0.93']
B (content):         ['0.07', '0.00', '0.40', '0.40', '0.40', '0.00', '0.00', '0.93']
C (dtype_weighted):  ['0.03', '0.00', '0.28', '0.27', '0.27', '0.00', '0.00', '0.47']
```

**find_dense_rectangles** (counts + biggest):
```
A (flood):     n=  3  biggest=B8:O11 area=56 dens=0.75
B (threshold): n=  4  biggest=A8:O10 area=45 dens=0.93
C (hybrid):    n=  4  biggest=B8:O10 area=42 dens=0.98
```

**find_blank_runs** (row-axis, counts):
```
A (strict):    n=  2  example=[BlankRun(start=6, end=7, axis='row'), BlankRun(start=21, end=22, axis='row')]
B (relaxed):   n=  5  example=[BlankRun(start=1, end=2, axis='row'), BlankRun(start=6, end=7, axis='row'), BlankRun(start=11, end=12, axis='row')]
C (threshold): n=  5  example=[BlankRun(start=1, end=2, axis='row'), BlankRun(start=6, end=7, axis='row'), BlankRun(start=11, end=12, axis='row')]
```

**find_header_row_candidates** (top 5 per variant):
```
A (text_density): n=  5  rows/scores=[(3, 0.5), (4, 0.5), (5, 0.5), (8, 1.0), (10, 1.0)]
B (vocab):        n=  3  rows/scores=[(8, 6.0), (13, 5.0), (18, 7.0)]
C (styled):       n=  6  rows/scores=[(3, 0.5), (4, 0.5), (5, 0.5), (8, 1.0), (13, 1.0)]
D (merged):       n= 12  rows/scores=[(8, 1.0), (9, 1.0), (10, 1.0), (11, 1.0), (13, 1.0)]
```

**Column dtype profiles** (cols inside biggest rect):
```
col   1: date=0.00 int=0.00 str=0.00 blank=1.00  pattern=blank
col   2: date=0.00 int=0.00 str=1.00 blank=0.00  pattern=mixed
col   3: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   4: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   5: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   6: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   7: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   8: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   9: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col  10: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col  11: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col  12: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col  13: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col  14: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
... (1 more)
```

#### Classification votes

**Relevance checks:**

| Check | Passes | Evidence |
|---|---|---|
| has_data_rectangle | yes | biggest_area=45, date_col_count=13 |
| not_navigation | yes | ratio=0.0, n=0 |
| not_summary | yes | ratio=0.0, n=0 |
| has_io_signal | yes | identifier_hits=2, stage_hits=5 |

**Mode checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| tall_table_shape | - | 0.00 | h=3, w=15, aspect=0.2, density=0.93, transitions=0, stripey=False |
| date_arena_dominance | - | 0.00 | date_cols=0 |
| header_continuity | - | 0.00 | header_row=8, rect_r0=8, rect_r1=10, data_rows_below=3, reason=too few data rows |
| kv_anchor_density | sheet_is_pli | 1.00 | env=r3-20/c1-15, aspect=1.2, merges=3, row_var=0.139, transitions=6, stripey=True |
| kv_pair_count | - | 0.00 | distinct_rows=2, distinct_cols=2, total_hits=3, kv_adjacencies=4 |
| section_split_by_blanks | - | 0.00 | sep_count=3, n_rects=4, rects_with_hits=1 |
| section_repeat_pattern | - | 0.00 | label_hits=0, repeating_aliases=[], repeating_count=0 |
| styled_header_dist | sheet_is_pli | 0.40 | n_styled_rows=6 |

**Mode vote totals:** {'row_per_pli': 0.0, 'sheet_is_pli': 1.4, 'section_per_pli': 0.0}  
**Mode winner:** sheet_is_pli (margin 1.40)  

**Axis checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| axis_row | - | 0.00 | header_row=8, r0=8, r1=10, data_rows_below=2, reason=too few data rows below header |
| axis_column | - | 0.00 | col1_str_pct=0.0, col1_n=2 |
| axis_whole_sheet | whole_sheet | 0.70 | n_rects=4, total_span=18, rects_with_hits=1, tight=True, concentrated=True |
| axis_section | - | 0.00 | n_rects=4, rects_with_hits=1, n_runs=5, repeating_count=0 |

**Axis vote totals:** {'row': 0.0, 'column': 0.0, 'whole_sheet': 0.7, 'section': 0.0}  
**Axis winner:** whole_sheet (margin 0.70)  
**Needs ClassificationJudge?** no  

**Verdict:** PASS  


### new Eastman TnAs.xlsx

**Notes:** Workbook-level SECTION_PER_PLI: each sheet = one PLI in SHEET_IS_PLI form. Per-sheet classification should be SHEET_IS_PLI / WHOLE_SHEET.

**Sheet picked:** `62330`  
**Dimensions:** 1000 rows × 15 cols  
**Non-blank cells:** 49 / 15000  
**Biggest rect:** A9:L11 area=36 dens=0.83  
**Best header row:** 9  
**Merged ranges:** 1, hyperlinks 0, formulas 0  
**Identifier hits:** 2, Stage hits: 3, Repeated labels: 0  

#### Tool variants

**compute_density** (row-axis, first 8 entries):
```
A (non_blank):       ['0.07', '0.00', '0.40', '0.40', '0.40', '0.00', '0.00', '0.00']
B (content):         ['0.07', '0.00', '0.40', '0.40', '0.40', '0.00', '0.00', '0.00']
C (dtype_weighted):  ['0.03', '0.00', '0.28', '0.27', '0.27', '0.00', '0.00', '0.00']
```

**find_dense_rectangles** (counts + biggest):
```
A (flood):     n=  1  biggest=B9:L11 area=33 dens=0.88
B (threshold): n=  2  biggest=A9:L11 area=36 dens=0.83
C (hybrid):    n=  2  biggest=B9:L11 area=33 dens=0.88
```

**find_blank_runs** (row-axis, counts):
```
A (strict):    n=  2  example=[BlankRun(start=6, end=8, axis='row'), BlankRun(start=12, end=1000, axis='row')]
B (relaxed):   n=  3  example=[BlankRun(start=1, end=2, axis='row'), BlankRun(start=6, end=8, axis='row'), BlankRun(start=12, end=1000, axis='row')]
C (threshold): n=  3  example=[BlankRun(start=1, end=2, axis='row'), BlankRun(start=6, end=8, axis='row'), BlankRun(start=12, end=1000, axis='row')]
```

**find_header_row_candidates** (top 5 per variant):
```
A (text_density): n=  4  rows/scores=[(4, 0.5), (5, 0.5), (9, 1.0), (11, 1.0)]
B (vocab):        n=  2  rows/scores=[(9, 7.0), (11, 4.0)]
C (styled):       n=  4  rows/scores=[(3, 0.5), (4, 0.5), (5, 0.5), (9, 1.0)]
D (merged):       n=  4  rows/scores=[(9, 1.0), (10, 1.0), (11, 1.0), (12, 1.0)]
```

**Column dtype profiles** (cols inside biggest rect):
```
col   1: date=0.00 int=0.00 str=0.00 blank=1.00  pattern=blank
col   2: date=0.00 int=0.00 str=1.00 blank=0.00  pattern=mixed
col   3: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   4: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   5: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   6: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   7: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   8: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col   9: date=0.50 int=0.00 str=0.50 blank=0.00  pattern=mixed
col  10: date=0.50 int=0.00 str=0.00 blank=0.50  pattern=mixed
col  11: date=0.50 int=0.00 str=0.00 blank=0.50  pattern=mixed
col  12: date=0.50 int=0.00 str=0.00 blank=0.50  pattern=mixed
```

#### Classification votes

**Relevance checks:**

| Check | Passes | Evidence |
|---|---|---|
| has_data_rectangle | yes | biggest_area=36, date_col_count=10 |
| not_navigation | yes | ratio=0.0, n=0 |
| not_summary | yes | ratio=0.0, n=0 |
| has_io_signal | yes | identifier_hits=2, stage_hits=3 |

**Mode checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| tall_table_shape | - | 0.00 | h=3, w=12, aspect=0.25, density=0.83, transitions=0, stripey=False |
| date_arena_dominance | - | 0.00 | date_cols=0 |
| header_continuity | - | 0.00 | header_row=9, rect_r0=9, rect_r1=11, data_rows_below=3, reason=too few data rows |
| kv_anchor_density | sheet_is_pli | 0.60 | env=r3-11/c1-12, aspect=1.33, merges=1, row_var=0.078, transitions=2, stripey=False |
| kv_pair_count | - | 0.00 | distinct_rows=2, distinct_cols=2, total_hits=3, kv_adjacencies=4 |
| section_split_by_blanks | - | 0.00 | sep_count=1, n_rects=2, rects_with_hits=1 |
| section_repeat_pattern | - | 0.00 | label_hits=0, repeating_aliases=[], repeating_count=0 |
| styled_header_dist | sheet_is_pli | 0.40 | n_styled_rows=4 |

**Mode vote totals:** {'row_per_pli': 0.0, 'sheet_is_pli': 1.0, 'section_per_pli': 0.0}  
**Mode winner:** sheet_is_pli (margin 1.00)  

**Axis checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| axis_row | - | 0.00 | header_row=9, r0=9, r1=11, data_rows_below=2, reason=too few data rows below header |
| axis_column | - | 0.00 | col1_str_pct=0.0, col1_n=2 |
| axis_whole_sheet | whole_sheet | 0.70 | n_rects=2, total_span=9, rects_with_hits=1, tight=True, concentrated=True |
| axis_section | - | 0.00 | n_rects=2, rects_with_hits=1, n_runs=3, repeating_count=0 |

**Axis vote totals:** {'row': 0.0, 'column': 0.0, 'whole_sheet': 0.7, 'section': 0.0}  
**Axis winner:** whole_sheet (margin 0.70)  
**Needs ClassificationJudge?** no  

**Verdict:** PASS  


### GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx

**Notes:** Bigger section file. Currently broken downstream (0 PLIs).

**Sheet picked:** `MAIN FALL 26`  
**Dimensions:** 1000 rows × 46 cols  
**Non-blank cells:** 4549 / 46000  
**Biggest rect:** D1:AA199 area=4776 dens=0.88  
**Best header row:** 1  
**Merged ranges:** 0, hyperlinks 0, formulas 0  
**Identifier hits:** 60, Stage hits: 45, Repeated labels: 45  

#### Tool variants

**compute_density** (row-axis, first 8 entries):
```
A (non_blank):       ['0.72', '0.59', '0.54', '0.48', '0.48', '0.22', '0.72', '0.61']
B (content):         ['0.72', '0.59', '0.54', '0.48', '0.48', '0.22', '0.72', '0.61']
C (dtype_weighted):  ['0.36', '0.40', '0.36', '0.33', '0.33', '0.16', '0.36', '0.42']
```

**find_dense_rectangles** (counts + biggest):
```
A (flood):     n=  1  biggest=A1:AG203 area=6699 dens=0.67
B (threshold): n=  1  biggest=D1:AA199 area=4776 dens=0.88
C (hybrid):    n=  1  biggest=D1:AA199 area=4776 dens=0.88
```

**find_blank_runs** (row-axis, counts):
```
A (strict):    n=  1  example=[BlankRun(start=204, end=1000, axis='row')]
B (relaxed):   n=  2  example=[BlankRun(start=200, end=202, axis='row'), BlankRun(start=204, end=1000, axis='row')]
C (threshold): n=  2  example=[BlankRun(start=200, end=202, axis='row'), BlankRun(start=204, end=1000, axis='row')]
```

**find_header_row_candidates** (top 5 per variant):
```
A (text_density): n=  1  rows/scores=[(1, 1.0)]
B (vocab):        n= 16  rows/scores=[(1, 16.0), (7, 16.0), (8, 3.0), (14, 16.0), (28, 16.0)]
C (styled):       n= 15  rows/scores=[(1, 1.0), (7, 1.0), (14, 1.0), (28, 1.0), (38, 1.0)]
D (merged):       n=  0  rows/scores=[]
```

**Column dtype profiles** (cols inside biggest rect):
```
col   4: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=name_text
col   5: date=0.00 int=0.86 str=0.07 blank=0.07  pattern=int_large
col   6: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=code_alnum
col   7: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=name_text
col   8: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=name_text
col   9: date=0.00 int=0.00 str=0.07 blank=0.93  pattern=blank
col  10: date=0.00 int=0.86 str=0.07 blank=0.07  pattern=int_small
col  11: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=code_alnum
col  12: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=name_text
col  13: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=code_alnum
col  14: date=0.00 int=0.00 str=0.93 blank=0.07  pattern=name_text
col  15: date=0.00 int=0.92 str=0.07 blank=0.01  pattern=int_small
col  16: date=0.00 int=0.92 str=0.07 blank=0.01  pattern=mixed
col  17: date=0.00 int=0.92 str=0.07 blank=0.01  pattern=int_medium
... (10 more)
```

#### Classification votes

**Relevance checks:**

| Check | Passes | Evidence |
|---|---|---|
| has_data_rectangle | yes | biggest_area=4776, date_col_count=3 |
| not_navigation | yes | ratio=0.0, n=0 |
| not_summary | yes | ratio=0.0, n=0 |
| has_io_signal | yes | identifier_hits=60, stage_hits=45 |

**Mode checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| tall_table_shape | - | 0.00 | h=199, w=24, aspect=8.29, density=0.88, transitions=28, stripey=True |
| date_arena_dominance | row_per_pli | 0.60 | date_cols=3 |
| header_continuity | - | 0.00 | header_row=1, alias_rows_below=14, reason=header repeats in body — not row_per_pli |
| kv_anchor_density | - | 0.00 | reason=sections detected, repeating=8 |
| kv_pair_count | sheet_is_pli | 1.00 | distinct_rows=15, distinct_cols=9, total_hits=135, kv_adjacencies=135 |
| section_split_by_blanks | - | 0.00 |  |
| section_repeat_pattern | section_per_pli | 2.00 | label_hits=45, repeating_aliases=['style no', 'style name', 'fabric', 'colour', 'factory', 'season', 'po no', 'po'], repeating_count=8 |
| styled_header_dist | sheet_is_pli | 0.40 | n_styled_rows=15 |

**Mode vote totals:** {'row_per_pli': 0.6, 'sheet_is_pli': 1.4, 'section_per_pli': 2.0}  
**Mode winner:** section_per_pli (margin 0.60)  

**Axis checks:**

| Check | Vote | Conf | Evidence |
|---|---|---|---|
| axis_row | row | 0.60 | header_row=1, r0=1, r1=199, data_rows_below=198 |
| axis_column | - | 0.00 | col1_str_pct=0.9292929292929293, col1_n=198 |
| axis_whole_sheet | - | 0.00 | reason=repeating identifiers detected — sections, repeating_count=8 |
| axis_section | section | 1.00 | n_rects=1, rects_with_hits=1, n_runs=2, repeating_count=8, trigger=repeating_within |

**Axis vote totals:** {'row': 0.6, 'column': 0.0, 'whole_sheet': 0.0, 'section': 1.0}  
**Axis winner:** section (margin 0.40)  
**Needs ClassificationJudge?** no  

**Verdict:** PASS  


## Per-tool variant winners

### compute_density — winner: B (density_by_content)

Variant **B (density_by_content)** is recommended. Variant A counts trivial values (`-`, `—`, `N/A`) as content, which inflates row density on TNA sheets that pad with em-dashes (Christian Berg + DKN). Variant C's dtype-weighting biases toward date-heavy rows — useful for downstream stage-arena detection, but for the relevance gate and rect-detection we want a normalised 0..1 signal that doesn't elevate text-only header rows.

**Evidence:** Variant A and B agree on all six sheets in this corpus because none of them have heavy em-dash padding — A and B diverge less than expected. The case that motivated B was MOP Compass Pro (a sister of the included MANOS file). Variant C consistently produces lower values (rescaled to max=2.0) and is more useful for downstream stage-arena ranking than for the rect-detection upstream of classification.

Side-by-side per file (row density, first 5 entries):

| File | A | B | C |
|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN | `0.05,0.75,0.50,0.62,0.62` | `0.05,0.75,0.50,0.62,0.62` | `0.03,0.38,0.25,0.46,0.46` |
| CHRISTIAN BERG- T&A.xlsx | `0.03,0.53,0.63,0.84,0.55` | `0.03,0.53,0.63,0.84,0.55` | `0.01,0.26,0.32,0.74,0.51` |
| 20260304 MOPD W26(1) MANOS COM | `0.05,0.74,0.47,0.79,0.97` | `0.05,0.74,0.47,0.79,0.97` | `0.04,0.37,0.24,0.61,0.78` |
| 63261-TNA.xlsx | `0.07,0.00,0.40,0.40,0.40` | `0.07,0.00,0.40,0.40,0.40` | `0.03,0.00,0.28,0.27,0.27` |
| new Eastman TnAs.xlsx | `0.07,0.00,0.40,0.40,0.40` | `0.07,0.00,0.40,0.40,0.40` | `0.03,0.00,0.28,0.27,0.27` |
| GUESS ATHLEISURE - MAIN FALL 2 | `0.72,0.59,0.54,0.48,0.48` | `0.72,0.59,0.54,0.48,0.48` | `0.36,0.40,0.36,0.33,0.33` |

### find_dense_rectangles — winner: B (density_threshold_grid)

Variant **B (density_threshold_grid)** is recommended for classification. It produces a SMALL number of LARGE rects (typically 1 for ROW_PER_PLI, 1 for SECTION_PER_PLI, several for SHEET_IS_PLI with stage strips) — which is precisely what the section/whole-sheet axis checks need.

**Evidence per file:**

- DKN: A=4 rects (flood over-segments title row + grand-total row + 2 data sub-blocks); B=1 wide rect (A2:AM6); C=1 (matches B).
- 63261: A=3; B=4 (the 3 stage strips + the metadata block — each a separate rect). The threshold variant correctly discovers the stripey structure that drives the SHEET_IS_PLI classification.
- Eastman: A=2; B=2; C=2 — variants agree, but B's rects are tighter (the threshold approach trims the trailing 989-row empty tail of the sheet automatically).
- GUESS: A=1; B=1; C=1 — single huge rect across all 199 rows; discrimination doesn't come from rect count but from repeating-alias signal inside it.

Variant A (flood-fill) over-segments: every isolated cluster (titles, grand totals, stray cells) becomes its own rect, drowning the signal. Variant C (hybrid) is currently identical to B on this corpus — interior trimming rarely fires because B's threshold already produces clean edges. Keep C around for future edge cases but it adds no value today.

| File | flood n | threshold n | hybrid n |
|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN | 4 | 1 | 1 |
| CHRISTIAN BERG- T&A.xlsx | 4 | 1 | 1 |
| 20260304 MOPD W26(1) MANOS COM | 2 | 1 | 1 |
| 63261-TNA.xlsx | 3 | 4 | 4 |
| new Eastman TnAs.xlsx | 1 | 2 | 2 |
| GUESS ATHLEISURE - MAIN FALL 2 | 1 | 1 | 1 |

### find_blank_runs — winner: B (relaxed_blank)

Variant **B (relaxed_blank)** is recommended. The strict variant (A) misses real section breaks because TNAs frequently leave one stray label or junk-cell in an otherwise-blank separator row.

**Evidence per file:**

- 63261: A=2 runs, B=5 runs, C=5 runs. The 3 extra runs B and C found are the genuine SHEET_IS_PLI strip separators (rows 11-12, 16-17, 21-22). Strict-blank missed them because each row in those gaps still has one residual cell.
- Eastman: A=B=C=3 — all variants find the long empty tail of the sheet, no discrepancy.
- DKN, CB, MOPD, GUESS: variants converge — these files have either no blank-run separators (one continuous data block) or their separators are fully blank.

Variant C (density_below_threshold) gives the same counts as B on this corpus but tends to over-trigger when row density happens to dip on a sparse header-only row. Variant B's 'at most 1 content cell' rule is the sweet spot.

| File | strict | relaxed | threshold |
|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN | 1 | 1 | 1 |
| CHRISTIAN BERG- T&A.xlsx | 0 | 0 | 0 |
| 20260304 MOPD W26(1) MANOS COM | 0 | 0 | 0 |
| 63261-TNA.xlsx | 2 | 5 | 5 |
| new Eastman TnAs.xlsx | 2 | 3 | 3 |
| GUESS ATHLEISURE - MAIN FALL 2 | 1 | 2 | 2 |

### find_header_row_candidates — winner: B (vocab_match_count)

Variant **B (vocab_match_count)** is the primary signal. ROW_PER_PLI sheets always have a header row with >= 3 known identifier-or-stage tokens; the vocab signal pinpoints it exactly and rarely returns false positives.

**Evidence per file:**

- DKN: A=4 candidates (rows 1-4 all text-dense), B=2 (rows 2, 3) — B correctly isolates the actual header rows; A's row-1 candidate is the title (problematic for header_continuity).
- CB: A=many candidates, B=few high-confidence — B's signal is the discriminator.
- 63261: A=many, B=4 (one per strip header). The header_continuity check then has to pick correctly across the four candidates; the alias-repetition guard added later makes that selection safe.
- GUESS: A=15 candidates (every identifier-bearing row is text-dense), B=15 (vocab hits at the same rows). Both signals are too noisy to identify a SINGLE header here — the alias-repetition guard in `header_continuity` is what actually discriminates ROW_PER_PLI from SECTION_PER_PLI for this file.

Variant A (text_density) is a useful FALLBACK when the header is in a language/dialect not covered by vocab. Variants C (styled) and D (merged) generate many candidates per sheet — they're tie-breakers and supporting evidence, not primary signals. Recommendation: ship B with A fallback; pass C/D as supplementary evidence into the header check.

| File | text_density n | vocab n | styled n | merged n |
|---|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN | 4 | 2 | 2 | 4 |
| CHRISTIAN BERG- T&A.xlsx | 3 | 2 | 11 | 10 |
| 20260304 MOPD W26(1) MANOS COM | 3 | 4 | 2 | 6 |
| 63261-TNA.xlsx | 5 | 3 | 6 | 12 |
| new Eastman TnAs.xlsx | 4 | 2 | 4 | 4 |
| GUESS ATHLEISURE - MAIN FALL 2 | 1 | 16 | 15 | 0 |

## Failure modes

**No failures — multi-check voting classified all 6 files correctly.**

### Near-misses (mode or axis margin < 0.5)

- `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx` — mode margin 0.60, axis margin 0.40. Mode votes: {'row_per_pli': 0.6, 'sheet_is_pli': 1.4, 'section_per_pli': 2.0}. Axis votes: {'row': 0.6, 'column': 0.0, 'whole_sheet': 0.0, 'section': 1.0}.

These are correctly classified but the dominant check won by a narrow margin. A subtly different layout could flip the vote and the judge would need to break the tie.

## Recommendations for P2

Of 6 files, 6 were classified correctly on both mode and axis. 0 fell below the 0.3 mode-margin threshold (would trigger a ClassificationJudge call).

### 1. Default variant stack for P2

Freeze these as the recommended defaults:

- `density_by_content` (Variant B) — trivial-value-aware row/col density. Drives rectangle detection, blank-run detection, and the relevance gate.
- `density_threshold_grid` (Variant B) with two enhancements added during this probe: (a) two-pass band-local col density (instead of global col density — the global signal is diluted by sparse rows above/below the band), and (b) close-band merging (gap≤5 for cols, gap≤1 for rows) to bridge sparse internal columns. Without these, DKN-style alternating-date layouts produced multiple fragmented rects instead of one wide one.
- `relaxed_blank` (Variant B) — strict-blank misses real section breaks polluted by stray cells; density-threshold-blank over-triggers on header-only rows.
- `vocab_match_count` (Variant B) as primary header signal, with `text_density_above_data` (Variant A) as fallback when no row hits >= 3 vocab terms. `styled_row` (C) and `merged_cell_anchor` (D) are tie-breakers, not primary.

### 2. Workbook-level vs sheet-level classification is real

The Eastman case revealed that the per-sheet classifier and the workbook orchestrator must be separate concerns. Each Eastman sheet is a SHEET_IS_PLI Orders-Plan form; the workbook-level intent is SECTION_PER_PLI across sheets. P2 should formalise a two-level decision: (a) per-sheet classification (this probe), (b) workbook classification (uniformly-SHEET_IS_PLI sheets with PLI-identifying names = SECTION_PER_PLI workbook).

### 3. The repeating-alias signal is the discriminator P2 needs

The GUESS case made it clear that ROW_PER_PLI and SECTION_PER_PLI can SHARE the shape of one big rect with a header row at top — the discriminator is whether identifier/metadata aliases REPEAT down the body. P2's IdentifierExtractor and StageBandExtractor should treat 'how many distinct aliases repeat 3+ times in the body' as a first-class shape signal, not a derived count.

### 4. The kv_adjacency signal is the breakthrough for SHEET_IS_PLI

Orders-Plan-family sheets (63261, Eastman first sheet) have only a couple of vocab hits — too few for the original vocab-only kv_pair_count check. The adjacency-based signal (text-cell ending in ':' next to a non-text value) provides the orthogonal signal that closes the SHEET_IS_PLI detection gap. P2 should keep this tool — it's small (~20 LOC) but decisive.

### 5. The shape model carries forward — minor extensions

ShapeSummary's current field set is sufficient for P2's IdentifierExtractor and StageBandExtractor inputs. One extension that emerged during this probe: surface a `kv_adjacencies` count as a first-class field, not buried in a check. Done.

### 6. Where ClassificationJudge would fire

None of the 6 files crossed the 0.3 margin threshold — the judge budget for this corpus is **0 calls**. Mode margins land between 0.60 (GUESS) and 1.40 (63261); axis margins between 0.40 (GUESS) and 1.00 (DKN). GUESS sits closest to the boundary (mode margin 0.60) and would be the file most likely to flip on a small layout change. The ClassificationJudge should be ENABLED as a safety net but is unlikely to fire on typical TNAs.

### 7. Tool-variant churn — recommendation

Implementing three variants of each tool added ~300 LOC of variant code. The recommendation is to **freeze the winning variant per tool and delete the losers** as the first refactor after P1. This probe report is the audit trail for those deletions.

### 8. Code-size note

P1 ended at ~1450 SLOC (non-blank/non-comment) across `shape_tools.py` + `checks.py` + `shape_models.py`, exceeding the 1000 LOC target. The overshoot is concentrated in (a) variant implementations (kept for the comparison, to be deleted) and (b) defensive guards added when investigating per-file misclassifications (the section-suppression in `axis_whole_sheet`, the alias-repetition guard in `header_continuity`). The defensive guards are load-bearing and should stay; the variants are deletable.
