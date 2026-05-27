"""query_spec / query_phase / query_all — match canvas cells against spec aliases.

Bridges canvas measurements to the app.specs catalogue. Header / identifier
/ stage detection uses the actual spec aliases (no hardcoded term lists)
plus word-boundary matching for short aliases and per-canonical reject
phrases for anti-pattern enforcement.

Three query granularities:
  - all_specs                — full catalog (every phase)
  - query_phase(phase)       — one of 'identifier' / 'stage' / 'subfield' / 'metadata'
  - query_spec(spec)         — one specific FieldSpec / StageSpec / SubfieldSpec
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from openpyxl.utils import column_index_from_string, get_column_letter

from app.artifacts.canvas import GridCanvas
from app.specs.enums import LabelMatchMode
from app.specs.identifiers import IDENTIFIER_SPECS
from app.specs.metadata import METADATA_SPECS
from app.specs.stages import STAGE_SPECS
from app.specs.subfields import SUBFIELD_SPECS
from app.tools._decorator import tool


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


@tool("text_dense_rows")
def text_dense_rows(canvas: GridCanvas, min_str_count: int = 2) -> set[int]:
    """1-indexed rows where strings dominate. Used to pre-filter spec queries
    so we don't scan thousands of data rows looking for header labels."""
    from app.tools.canvas.build import DTYPE_STR
    out = set()
    for r in range(canvas.n_rows):
        strs = sum(1 for c in range(canvas.n_cols) if canvas.channels["dtype"][r][c] == DTYPE_STR)
        if strs >= min_str_count:
            out.add(r + 1)
    return out


def text_dense_cols(canvas: GridCanvas, min_str_count: int = 2) -> set[int]:
    """1-indexed cols where strings dominate."""
    from app.tools.canvas.build import DTYPE_STR
    out = set()
    for c in range(canvas.n_cols):
        strs = sum(1 for r in range(canvas.n_rows) if canvas.channels["dtype"][r][c] == DTYPE_STR)
        if strs >= min_str_count:
            out.add(c + 1)
    return out


@tool("query_spec")
def query_spec(canvas: GridCanvas, spec,
               restrict_rows: set[int] | None = None,
               restrict_cols: set[int] | None = None) -> list[SpecMatch]:
    """Find every cell whose normalised text matches ANY alias of `spec`.
    Skips merge-continuation cells.

    `restrict_rows` / `restrict_cols` are sets of 1-indexed positions. If
    given, ONLY those rows/cols are scanned — useful when you already know
    the header zone (saves work on 1000-row sheets).
    """
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


@tool("query_phase")
def query_phase(canvas: GridCanvas, phase: str,
                restrict_rows: set[int] | None = None,
                restrict_cols: set[int] | None = None) -> list[SpecMatch]:
    """Run query_spec across every spec in `phase` ('identifier'/'stage'/'subfield'/'metadata')."""
    out = []
    for spec in specs_for_phase(phase):
        out.extend(query_spec(canvas, spec, restrict_rows, restrict_cols))
    return out


@tool("query_all")
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


@tool("find_header_rows_via_specs")
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



def spec_summary(spec) -> dict:
    """For reporting: surface the spec's aliases + anti_patterns + examples."""
    return {
        "canonical":      spec.canonical,
        "match_mode":     spec.label_match_mode.value,
        "aliases":        list(spec.aliases),
        "anti_patterns":  list(getattr(spec, "anti_patterns", [])),
        "examples":       list(getattr(spec, "examples", [])),
    }
