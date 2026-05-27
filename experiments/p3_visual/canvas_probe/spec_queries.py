"""Bridge from canvas measurements → experiments/specs/ catalog.

Lets header/identifier/stage detection use the actual spec aliases (not
hardcoded term lists). Each spec contributes:
  - aliases             → matched against cell text
  - label_match_mode    → weight for the match (HARD/MEDIUM/SOFT)
  - anti_patterns       → carried through as transparency context (descriptive,
                          shown in reports; not yet used as filters)

Three query granularities:
  - all_specs                — full catalog (every phase)
  - query_phase(phase)       — one of 'identifier' / 'stage' / 'subfield' / 'metadata'
  - query_spec(spec)         — one specific FieldSpec / StageSpec / SubfieldSpec
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from openpyxl.utils import column_index_from_string

# Add experiments/ root so we can import specs package
_EXP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_EXP_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXP_ROOT))

from specs.identifiers import IDENTIFIER_SPECS
from specs.stages import STAGE_SPECS
from specs.subfields import SUBFIELD_SPECS
from specs.metadata import METADATA_SPECS
from specs.enums import LabelMatchMode

from build_canvas import GridCanvas


# Match-mode → score multiplier
MATCH_MODE_WEIGHT = {
    LabelMatchMode.HARD:   1.0,
    LabelMatchMode.MEDIUM: 0.85,
    LabelMatchMode.SOFT:   0.6,
}


@dataclass
class SpecMatch:
    row:        int           # 1-indexed
    col:        str           # column letter
    canonical:  str           # which spec's canonical
    phase:      str           # 'identifier' / 'stage' / 'subfield' / 'metadata'
    alias:      str           # which alias matched
    cell_text:  str           # the actual cell content
    weight:     float         # spec.label_match_mode weight


def _phase_of(spec) -> str:
    """Determine which phase a spec belongs to by checking which registry contains it."""
    if spec in IDENTIFIER_SPECS: return "identifier"
    if spec in STAGE_SPECS:      return "stage"
    if spec in SUBFIELD_SPECS:   return "subfield"
    if spec in METADATA_SPECS:   return "metadata"
    return "unknown"


def all_specs() -> list:
    """Return the full catalog — every spec across every phase."""
    return list(IDENTIFIER_SPECS) + list(STAGE_SPECS) + list(SUBFIELD_SPECS) + list(METADATA_SPECS)


def specs_for_phase(phase: str) -> list:
    return {
        "identifier": list(IDENTIFIER_SPECS),
        "stage":      list(STAGE_SPECS),
        "subfield":   list(SUBFIELD_SPECS),
        "metadata":   list(METADATA_SPECS),
        "all":        all_specs(),
    }.get(phase, [])


def text_dense_rows(canvas: GridCanvas, min_str_count: int = 2) -> set[int]:
    """1-indexed rows where strings dominate. Used to pre-filter spec queries
    so we don't scan thousands of data rows looking for header labels."""
    from build_canvas import DTYPE_STR
    out = set()
    for r in range(canvas.n_rows):
        strs = sum(1 for c in range(canvas.n_cols) if canvas.channels["dtype"][r][c] == DTYPE_STR)
        if strs >= min_str_count:
            out.add(r + 1)
    return out


def text_dense_cols(canvas: GridCanvas, min_str_count: int = 2) -> set[int]:
    """1-indexed cols where strings dominate."""
    from build_canvas import DTYPE_STR
    out = set()
    for c in range(canvas.n_cols):
        strs = sum(1 for r in range(canvas.n_rows) if canvas.channels["dtype"][r][c] == DTYPE_STR)
        if strs >= min_str_count:
            out.add(c + 1)
    return out


def query_spec(canvas: GridCanvas, spec,
               restrict_rows: set[int] | None = None,
               restrict_cols: set[int] | None = None) -> list[SpecMatch]:
    """Find every cell whose normalised text matches ANY alias of `spec`.
    Skips merge-continuation cells.

    `restrict_rows` / `restrict_cols` are sets of 1-indexed positions. If
    given, ONLY those rows/cols are scanned — useful when you already know
    the header zone (saves work on 1000-row sheets).
    """
    import re
    norm_aliases = [a.strip().lower() for a in (spec.aliases or [])]
    if not norm_aliases:
        return []
    weight = MATCH_MODE_WEIGHT.get(spec.label_match_mode, 0.7)
    phase  = _phase_of(spec)

    # Per-canonical reject phrases — labels containing any of these tokens
    # belong to stage_metadata or a sibling concept, NOT this canonical.
    # Encodes anti_patterns as machine-readable rejection rules.
    REJECT_PHRASES = {
        "quantity":     ("cut qty", "shipped qty", "sewn qty", "ship qty",
                         "received qty", "approved qty", "rcvd qty",
                         "qty cut", "qty shipped", "qty sewn", "qty received",
                         "mats qty"),
        "style_code":   ("style description",),
        "color_code":   ("color description", "colour description"),
        "fabric_code":  ("fabric description", "fab description"),
        "io_number":    ("description", "submission", "inspection",
                         "consumption", "deviation"),
        "delivery_date":(),
        "shipment_date":("ex factory shipment",),
        "ex_fty_date":  (),
    }
    reject = REJECT_PHRASES.get(spec.canonical, ())

    # Pre-compile word-boundary regexes for SHORT aliases (≤4 chars).
    # Substring matching on a 2-char alias like "io" matches "descript-IO-n",
    # "submiss-IO-n", "inspect-IO-n" — false positives that crush precision.
    # Longer aliases ("buyer po no") are descriptive enough that substring
    # containment is safe.
    SHORT_LEN = 4
    short_patterns: dict[str, "re.Pattern"] = {
        a: re.compile(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])")
        for a in norm_aliases if len(a) <= SHORT_LEN
    }

    # Build merge-continuation set
    cont = set()
    for (r0, c0, r1, c1) in canvas.merge_ranges:
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                if (rr, cc) != (r0, c0): cont.add((rr, cc))

    matches: list[SpecMatch] = []
    from openpyxl.utils import get_column_letter
    for r in range(canvas.n_rows):
        if restrict_rows is not None and (r + 1) not in restrict_rows: continue
        for c in range(canvas.n_cols):
            if restrict_cols is not None and (c + 1) not in restrict_cols: continue
            row_1, col_1 = r + 1, c + 1
            if (row_1, col_1) in cont: continue
            v = canvas.cell_values[r][c]
            if not isinstance(v, str): continue
            haystack = v.strip().lower()
            if not haystack: continue
            # Reject phrases — anti-pattern enforcement
            if reject and any(p in haystack for p in reject): continue
            for alias in norm_aliases:
                if not alias: continue
                if alias in short_patterns:
                    hit = bool(short_patterns[alias].search(haystack))
                else:
                    hit = (haystack == alias or alias in haystack)
                if hit:
                    matches.append(SpecMatch(
                        row=row_1,
                        col=get_column_letter(col_1),
                        canonical=spec.canonical,
                        phase=phase,
                        alias=alias,
                        cell_text=v,
                        weight=weight,
                    ))
                    break
    return matches


def query_phase(canvas: GridCanvas, phase: str,
                restrict_rows: set[int] | None = None,
                restrict_cols: set[int] | None = None) -> list[SpecMatch]:
    out = []
    for spec in specs_for_phase(phase):
        out.extend(query_spec(canvas, spec, restrict_rows, restrict_cols))
    return out


def query_all(canvas: GridCanvas,
              restrict_rows: set[int] | None = None,
              restrict_cols: set[int] | None = None) -> list[SpecMatch]:
    return query_phase(canvas, "all", restrict_rows, restrict_cols)


def aggregate_by_row(matches: list[SpecMatch]) -> dict[int, dict]:
    """Per-row aggregate: {row_idx: {phase: weighted_count, canonicals: set, total: float}}."""
    out: dict[int, dict] = {}
    for m in matches:
        d = out.setdefault(m.row, {"total": 0.0, "phases": {}, "canonicals": set()})
        d["total"] += m.weight
        d["phases"][m.phase] = d["phases"].get(m.phase, 0.0) + m.weight
        d["canonicals"].add(m.canonical)
    return out


def aggregate_by_col(matches: list[SpecMatch]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in matches:
        d = out.setdefault(m.col, {"total": 0.0, "phases": {}, "canonicals": set()})
        d["total"] += m.weight
        d["phases"][m.phase] = d["phases"].get(m.phase, 0.0) + m.weight
        d["canonicals"].add(m.canonical)
    return out


def find_header_rows_via_specs(
    canvas: GridCanvas,
    phase_weights: dict[str, float] = None,
    min_score: float = 1.0,
) -> list[tuple[int, float, dict]]:
    """Score every row by spec-alias hits.

    phase_weights tune importance per phase. Default: identifier=2.0, stage=1.0,
    subfield=0.5, metadata=1.0 (raise identifier weight since the identifier
    header row is the typical anchor).

    Returns: list of (row_idx, total_score, breakdown_dict) sorted desc.
    """
    if phase_weights is None:
        phase_weights = {"identifier": 2.0, "stage": 1.0, "subfield": 0.5, "metadata": 1.0}

    # Pre-filter: only scan text-dense rows (header rows are by definition
    # rows with multiple string cells). On a 1000-row GUESS sheet this cuts
    # the search space from 1000 to <50 rows.
    candidate_rows = text_dense_rows(canvas, min_str_count=2)
    matches = query_all(canvas, restrict_rows=candidate_rows)
    per_row = aggregate_by_row(matches)
    scores = []
    for row, info in per_row.items():
        # Skip empty rows
        if canvas.channels["empty_row"][row - 1][0] == 1: continue
        score = sum(
            phase_weights.get(phase, 1.0) * count
            for phase, count in info["phases"].items()
        )
        breakdown = {phase: round(count * phase_weights.get(phase, 1.0), 2)
                     for phase, count in info["phases"].items()}
        scores.append((row, round(score, 2), breakdown))
    scores.sort(key=lambda x: -x[1])
    return [s for s in scores if s[1] >= min_score]


def find_field_label_cells(canvas: GridCanvas, phase: str = "all") -> dict[str, list[SpecMatch]]:
    """For each canonical, return cells matching its aliases.
    Useful for: "where in the sheet does fabric_code's label appear?"
    """
    out: dict[str, list[SpecMatch]] = {}
    for spec in specs_for_phase(phase):
        ms = query_spec(canvas, spec)
        if ms:
            out[spec.canonical] = ms
    return out


@dataclass
class KvFinding:
    """A label → value pair detected by adjacency."""
    canonical:    str                          # spec.canonical
    phase:        str                          # "identifier" / "metadata"
    label_coord:  str                          # "B3"
    value_coord:  str                          # "C3"
    value:        object                       # the resolved value
    direction:    str                          # "right" | "below" | "above" | "left"
    weight:       float                        # spec label match weight × dtype agreement
    dtype_ok:     bool                         # did the value cell match expected dtype


def _expected_canvas_dtype(spec) -> set[int] | None:
    """Map specs.enums.ValueDtype → canvas DTYPE_* int set.
    Returns None for ANY (no constraint).
    """
    from build_canvas import DTYPE_DATE, DTYPE_INT, DTYPE_FLOAT, DTYPE_STR
    from specs.enums import ValueDtype
    dt = getattr(spec, "value_dtype", None)
    if dt is None or dt == ValueDtype.ANY: return None
    if dt == ValueDtype.DATE: return {DTYPE_DATE}
    if dt == ValueDtype.INT:  return {DTYPE_INT, DTYPE_FLOAT}
    if dt == ValueDtype.STR:  return {DTYPE_STR}
    return None


def find_kv_identifiers(canvas: GridCanvas, phase: str = "identifier",
                         search_order: tuple[tuple[int, int], ...] =
                         ((0, 1), (1, 0), (-1, 0), (0, -1)),
                         exclude_header_rows: bool = True) -> list[KvFinding]:
    """For each label cell that matches an identifier (or metadata) spec, look
    in adjacent cells for a value of the expected dtype. Default search order:
    right, below, above, left.

    K:V extraction is the COMPLEMENT of tabular extraction. Label cells in
    header rows feed columnar (tabular) extraction; stray label cells outside
    header rows are k:v candidates (typical for SHEET_IS_PLI / scattered
    metadata blocks). When `exclude_header_rows` is True (default), labels
    sitting on rows detected as headers are skipped.
    """
    from build_canvas import DTYPE_BLANK
    from openpyxl.utils import get_column_letter

    # Identify rows that are TABULAR HEADER ROWS (multi-column label rows),
    # not just rows that happen to contain a label. K:V layouts often place
    # one label per row beside its value — those rows have only 1-2 identifier
    # matches and shouldn't be excluded from kv detection.
    header_rows: set[int] = set()
    if exclude_header_rows:
        try:
            scored = find_header_rows_via_specs(canvas, min_score=1.0)
            for r, _, _ in scored[:5]:
                # Count distinct identifier label columns on this row
                row_matches = [m for m in query_phase(canvas, phase, restrict_rows={r})]
                id_cols = {m.col for m in row_matches if m.phase == "identifier"}
                if len(id_cols) >= 3:
                    header_rows.add(r)
        except Exception:
            header_rows = set()

    # Visually label-like = bold OR has fill color. K:V labels in scattered
    # layouts are essentially always one of these (look at any SHEET_IS_PLI
    # metadata block). Data-row cells that happen to contain alias text are
    # filtered out by this gate.
    def _looks_like_label(row_1: int, col_letter: str) -> bool:
        r0 = row_1 - 1
        c0 = column_index_from_string(col_letter) - 1
        bold = canvas.channels["bold"][r0][c0] == 1
        filled = canvas.channels["fill_color"][r0][c0] > 0
        return bold or filled

    label_matches = [m for m in query_phase(canvas, phase)
                     if m.row not in header_rows and _looks_like_label(m.row, m.col)]
    spec_by_canon = {s.canonical: s for s in specs_for_phase(phase)}

    # Build a set of all label cells (to skip neighbours that are themselves labels)
    label_cells = {(m.row, column_index_from_string(m.col)) for m in label_matches}

    # Merge-continuation set (skip these as neighbours)
    cont = set()
    for (r0, c0, r1, c1) in canvas.merge_ranges:
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                if (rr, cc) != (r0, c0): cont.add((rr, cc))

    findings: list[KvFinding] = []
    dir_name = {(0, 1): "right", (1, 0): "below", (-1, 0): "above", (0, -1): "left"}

    for m in label_matches:
        spec = spec_by_canon.get(m.canonical)
        if spec is None: continue
        expected = _expected_canvas_dtype(spec)
        lr = m.row
        lc = column_index_from_string(m.col)

        for dr, dc in search_order:
            r2, c2 = lr + dr, lc + dc
            if r2 < 1 or c2 < 1 or r2 > canvas.n_rows or c2 > canvas.n_cols: continue
            if (r2, c2) in label_cells: continue  # neighbour is another label → header row
            if (r2, c2) in cont: continue          # neighbour is merge continuation
            val = canvas.cell_values[r2 - 1][c2 - 1]
            if val in (None, "", " "): continue
            dt = canvas.channels["dtype"][r2 - 1][c2 - 1]
            if dt == DTYPE_BLANK: continue
            dtype_ok = (expected is None) or (dt in expected)
            # weight = label weight × (1.0 if dtype matches else 0.4)
            w = m.weight * (1.0 if dtype_ok else 0.4)
            findings.append(KvFinding(
                canonical   = m.canonical,
                phase       = m.phase,
                label_coord = f"{m.col}{m.row}",
                value_coord = f"{get_column_letter(c2)}{r2}",
                value       = val,
                direction   = dir_name[(dr, dc)],
                weight      = round(w, 3),
                dtype_ok    = dtype_ok,
            ))
            break  # first non-empty non-label neighbour wins
    return findings


def find_tabular_identifiers(canvas: GridCanvas,
                              phase: str = "identifier",
                              max_data_rows: int = 1500) -> list[KvFinding]:
    """For each header-row label cell matching an identifier spec, claim its
    COLUMN as the value-column and emit one Finding per data row below the
    header band. This is the tabular complement of `find_kv_identifiers`.

    Covers ROW_PER_PLI (single header band) and SECTION_PER_PLI (repeating
    header rows treated as multiple header-band sections, each followed by
    one PLI block).
    """
    from build_canvas import DTYPE_BLANK
    from openpyxl.utils import get_column_letter

    # 1. Score header rows; we'll keep a small band, not just the top-1.
    header_scored = find_header_rows_via_specs(canvas, min_score=1.0)
    if not header_scored: return []

    spec_by_canon = {s.canonical: s for s in specs_for_phase(phase)}

    # Identifier-weighted score per row (so subfield-heavy rows don't outrank
    # rows that actually carry identifier labels).
    def _id_score(breakdown: dict) -> float:
        return breakdown.get("identifier", 0.0)

    # Detect repeating-header sections (SECTION_PER_PLI) by repeating-row id.
    rep = canvas.channels.get("repeating_row_id")
    section_starts: list[int] = []
    band_extent: dict[int, int] = {}   # section_start_row → header band end
    if rep is not None:
        top_rows = [r for r, _, _ in header_scored[:5]]
        group_ids = {rep[r-1][0] for r in top_rows if rep[r-1][0] != 0}
        if group_ids:
            for r in range(1, canvas.n_rows + 1):
                if rep[r-1][0] in group_ids:
                    section_starts.append(r)

    if not section_starts:
        # ROW_PER_PLI: pick the row with the most identifier hits as section
        # start. Then absorb any header-scored row directly adjacent into the
        # SAME band (multi-row headers are common — DKN: rows 1-3, CB: 2-3).
        best = max(header_scored, key=lambda x: _id_score(x[2]))
        section_starts = [best[0]]

    findings: list[KvFinding] = []

    # Pre-build header-rows set + per-row scores for band absorption
    scored_rows  = {r: (s, bd) for r, s, bd in header_scored}

    for i, header_row in enumerate(section_starts):
        # Header BAND = the section-start row plus contiguous scored rows
        # IMMEDIATELY ABOVE it (multi-row headers like DKN rows 1-3). We do
        # NOT walk downward: rows below the section start are data rows that
        # may incidentally score above threshold because identifier VALUES
        # often share substrings with alias text.
        band_rows = {header_row}
        cand = header_row - 1
        while cand >= 1 and cand in scored_rows:
            band_rows.add(cand)
            cand -= 1

        # 2. Within this band, find identifier label cells across ALL rows.
        #    Each match claims its anchor column AND every column in its
        #    horizontal merge span (the "FABRIC spans 5 cells" rule), gated
        #    by merge width (mega-merges are banners, not column headers).
        anchor_span: dict[tuple[int, int], tuple[int, int, int, int]] = {
            (mr[0], mr[1]): mr for mr in canvas.merge_ranges
        }
        MAX_HEADER_MERGE_COLS = 10

        matches = query_phase(canvas, phase, restrict_rows=band_rows)

        # Track, per claimed column, the (match, source-anchor) so we can
        # group columns by their parent merged band for sibling resolution.
        col_to_match: dict[int, SpecMatch] = {}
        col_to_anchor: dict[int, tuple[int, int] | None] = {}
        for m in matches:
            anchor_ci = column_index_from_string(m.col)
            span = anchor_span.get((m.row, anchor_ci))
            if span and span[0] == span[2]:
                width = span[3] - span[1] + 1
                if width <= MAX_HEADER_MERGE_COLS and width >= 2:
                    claim_cols = list(range(span[1], span[3] + 1))
                    src_anchor = (m.row, anchor_ci)
                else:
                    claim_cols = [anchor_ci]
                    src_anchor = None
            else:
                claim_cols = [anchor_ci]
                src_anchor = None
            for ci in claim_cols:
                prev = col_to_match.get(ci)
                if prev is None or m.weight > prev.weight:
                    col_to_match[ci]  = m
                    col_to_anchor[ci] = src_anchor

        # 2b. Sibling resolution under merged code-family bands.
        # If multiple columns were claimed under the same merged anchor with
        # a *_code canonical, treat them positionally:
        #   1st col → *_code  /  2nd col → *_name  /  3rd+ → drop (metadata)
        FAMILY_MAP = {
            "style_code":   ("style_code", "style_name"),
            "fabric_code":  ("fabric_code", "fabric_name"),
            "color_code":   ("color_code",  "color_name"),
        }
        from collections import defaultdict
        groups: dict[tuple[int, int], list[int]] = defaultdict(list)
        for ci, anchor in col_to_anchor.items():
            if anchor is not None:
                groups[anchor].append(ci)
        for anchor, cols in groups.items():
            cols.sort()
            base_m = col_to_match[cols[0]]
            family = FAMILY_MAP.get(base_m.canonical)
            if family is None: continue
            code_canon, name_canon = family
            # 1st col keeps the code canonical (already correct since it
            # inherited from the merged match). 2nd → name. 3rd+ → drop.
            for idx, ci in enumerate(cols):
                if idx == 0:
                    # rebuild SpecMatch with explicit code canonical
                    col_to_match[ci] = SpecMatch(
                        row=base_m.row, col=base_m.col, canonical=code_canon,
                        phase=base_m.phase, alias=base_m.alias,
                        cell_text=base_m.cell_text, weight=base_m.weight,
                    )
                elif idx == 1:
                    col_to_match[ci] = SpecMatch(
                        row=base_m.row, col=base_m.col, canonical=name_canon,
                        phase=base_m.phase, alias=base_m.alias,
                        cell_text=base_m.cell_text, weight=base_m.weight,
                    )
                else:
                    col_to_match.pop(ci, None)  # 3rd+ goes to metadata, not identifier

        if not col_to_match: continue

        # 2c. Single-column arbitration per canonical (per section).
        # A canonical like io_number or color_code should claim AT MOST ONE
        # column per PLI section. If multiple columns end up tagged with the
        # same canonical (e.g. both "IO No" and "Buyer Po No" headers), pick
        # the strongest by: alias-length (longer = more specific) → match
        # weight → leftmost column.
        SINGLE_CANONICAL = {
            "io_number", "style_code", "style_name", "color_code", "color_name",
            "fabric_code", "fabric_name", "quantity",
            "delivery_date", "shipment_date", "ex_fty_date",
        }
        canon_to_cols: dict[str, list[int]] = defaultdict(list)
        for ci, m in col_to_match.items():
            if m.canonical in SINGLE_CANONICAL:
                canon_to_cols[m.canonical].append(ci)
        for canon, cols in canon_to_cols.items():
            if len(cols) <= 1: continue
            # Rank by ALIAS POSITION in the spec (spec authors place more
            # specific aliases earlier — io_number's "io" / "internal order"
            # outranks "buyer po" by design).
            spec = spec_by_canon.get(canon)
            alias_rank = {a.strip().lower(): i for i, a in enumerate(spec.aliases or [])} if spec else {}
            def rank_key(ci):
                m = col_to_match[ci]
                return (alias_rank.get(m.alias, 9999), -m.weight, ci)
            cols.sort(key=rank_key)
            for ci in cols[1:]:
                col_to_match.pop(ci, None)

        # 2d. Bare "CODE" disambiguation. A header cell whose text is just
        # "code" (no family qualifier) is ambiguous. If it sits within ±2
        # columns of a header cell already claimed for the *_code family
        # (color/style/fabric), inherit that family.
        bare_code_canon: dict[str, str] = {
            "color_code": "color_code", "style_code": "style_code", "fabric_code": "fabric_code",
        }
        for br in band_rows:
            for ci in range(1, canvas.n_cols + 1):
                if ci in col_to_match: continue
                v = canvas.cell_values[br-1][ci-1]
                if not isinstance(v, str): continue
                if v.strip().lower() != "code": continue
                # Look ±2 cols for an existing *_code claim
                for off in (-2, -1, 1, 2):
                    nb = ci + off
                    if nb in col_to_match and col_to_match[nb].canonical in bare_code_canon:
                        canon = col_to_match[nb].canonical
                        col_to_match[ci] = SpecMatch(
                            row=br, col=get_column_letter(ci),
                            canonical=canon, phase="identifier",
                            alias="code", cell_text=v,
                            weight=col_to_match[nb].weight * 0.8,
                        )
                        break

        # Data rows start after the LAST row in the band
        header_row = max(band_rows)

        # 3. Data row range = below this header, above next section / blank-run / sheet end.
        next_section = section_starts[i+1] if i+1 < len(section_starts) else None
        data_start = header_row + 1
        # Skip sub-header rows that also scored as headers (e.g. DKN row 3 = "Plan/Actual")
        for sub_r, _, _ in header_scored:
            if sub_r == data_start and sub_r > header_row:
                data_start += 1
        data_end_cap = min(canvas.n_rows,
                           (next_section - 1) if next_section else canvas.n_rows,
                           header_row + max_data_rows)

        data_rows: list[int] = []
        consec_blank = 0
        for r in range(data_start, data_end_cap + 1):
            if canvas.channels["empty_row"][r-1][0] == 1:
                consec_blank += 1
                if consec_blank >= 2: break  # data section ended
                continue
            consec_blank = 0
            # Skip total/subtotal rows: any cell starts with "total"/"subtotal"/"grand total"
            is_total = False
            for c in range(min(canvas.n_cols, 4)):  # check first few cols
                v = canvas.cell_values[r-1][c]
                if isinstance(v, str):
                    t = v.strip().lower()
                    if t.startswith(("total", "subtotal", "grand total")):
                        is_total = True; break
            if is_total: continue
            data_rows.append(r)

        # 4. Emit one Finding per (canonical, data_row, claimed column)
        for r in data_rows:
            for ci, m in col_to_match.items():
                val = canvas.cell_values[r-1][ci-1]
                if val in (None, "", " "): continue  # legitimately absent
                dt = canvas.channels["dtype"][r-1][ci-1]
                if dt == DTYPE_BLANK: continue
                spec = spec_by_canon.get(m.canonical)
                expected = _expected_canvas_dtype(spec) if spec else None
                dtype_ok = (expected is None) or (dt in expected)
                findings.append(KvFinding(
                    canonical   = m.canonical,
                    phase       = m.phase,
                    label_coord = f"{m.col}{m.row}",
                    value_coord = f"{get_column_letter(ci)}{r}",
                    value       = val,
                    direction   = "below",  # tabular is always vertical
                    weight      = round(m.weight * (1.0 if dtype_ok else 0.4), 3),
                    dtype_ok    = dtype_ok,
                ))
    return findings


def kv_value_cells(findings: list[KvFinding]) -> set[tuple[int, int]]:
    """Convenience: 1-indexed (row, col) of all value cells claimed by k:v."""
    from openpyxl.utils import column_index_from_string
    out = set()
    for f in findings:
        # Parse coord like "AB12"
        col_part = "".join(ch for ch in f.value_coord if ch.isalpha())
        row_part = int("".join(ch for ch in f.value_coord if ch.isdigit()))
        out.add((row_part, column_index_from_string(col_part)))
    return out


def spec_summary(spec) -> dict:
    """For reporting: surface the spec's aliases + anti_patterns + examples."""
    return {
        "canonical":      spec.canonical,
        "match_mode":     spec.label_match_mode.value,
        "aliases":        list(spec.aliases),
        "anti_patterns":  list(getattr(spec, "anti_patterns", [])),
        "examples":       list(getattr(spec, "examples", [])),
    }
