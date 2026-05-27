"""Strategies for label-mapping sub-problems (#6 identity, #9 stage, #10 sub-field).

Each strategy has the same signature::

    fn(raw: str, sample_values: list[object] | None) -> MatchResult

so the harness can swap them out interchangeably.

A MatchResult bundles canonical (str | None), score (float), and ranked
candidates. score == 0.0 means "no match"; the harness scores a strategy
correct when result.canonical == expected_canonical (string equality on the
canonical token).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore[assignment]


# === canonical vocab tables ===================================================
# Aliases are normalised (lowercase, single spaces, no punctuation collapsed).

IDENTITY_VOCAB: dict[str, list[str]] = {
    "io_number": [
        "io", "io no", "io number", "io#", "ion", "buyer po", "buyer po no",
        "po no", "po number", "po", "job no", "job number", "purchase order",
    ],
    "style_code": [
        "style", "style no", "style number", "style code", "style#",
        "style id",
    ],
    "style_name": [
        "style name", "style description", "description", "garment",
        "garment description", "product", "product name",
    ],
    "color_code": [
        "color code", "colour code", "color no", "colour no", "color id",
        "code",
    ],
    "color_name": [
        "color", "colour", "color name", "colour name",
    ],
    "fabric_code": [
        "fabric", "fabric code", "fabric quality", "material", "fabric type",
        "fabric description",
    ],
    "fabric_quality": [
        "fabric quality", "quality",
    ],
    "delivery_date": [
        "delivery date", "ex fac", "ex fac date", "ex factory date",
        "ex-factory", "ex factory", "ex-fac date", "etd ex factory",
        "shipment date", "ship date", "etd", "etd ex factory as per p.o",
    ],
    "etd_ex_factory": [
        "etd ex factory", "etd ex-factory", "ex factory etd",
    ],
    "quantity": [
        "qty", "quantity", "order qty", "plan qty", "order quantity",
        "po qty", "total", "total qty",
    ],
    "order_receipt_date": [
        "order receipt", "order date", "original order received dt",
        "po date", "order received", "order received date",
    ],
    "buyer": [
        "buyer", "customer", "client",
    ],
    "season": [
        "season", "ct season", "customer season",
    ],
    "factory": [
        "factory", "unit", "plant",
    ],
    "article_no": [
        "article", "article no", "article number",
    ],
    "price": [
        "price", "cost", "fob", "unit price",
    ],
    "balance_qty": [
        "balance qty", "balance quantity", "bal qty",
    ],
    "buyer_po_no": [
        "buyer po no", "buyer po", "po no",
    ],
    "cut_qty": [
        "cut qty", "cutting qty", "cut quantity",
    ],
    "sewing_qty": [
        "sewing qty", "sewn qty",
    ],
    "shipped_qty": [
        "shipped qty", "shipment qty",
    ],
}


STAGE_VOCAB: dict[str, list[str]] = {
    "fabric": ["fabric", "fab", "fab plan"],
    "lab_dip_send": ["lab dip send", "l/d send", "ld send", "lab dip"],
    "lab_dip_approval": ["lab dip approval", "lab dip appl", "l/d appl", "ld appl"],
    "fit_send": ["fit send", "fit sent"],
    "fit_approval": ["fit approval", "fit appl", "fit appr"],
    "art_work_send": [
        "art work send", "a/w send", "aw send", "vap send", "art send",
        "vap 1 send", "vap 2 send",
    ],
    "art_work_approval": [
        "art work approval", "a/w appl", "aw appl", "art appl", "art appr",
        "vap rec", "vap 1 rec", "vap 2 rec",
    ],
    "in_house_fabric_send": [
        "fabric inhouse", "fabric in-house", "fabric in house", "fabric ih",
        "i/b fab send", "in-house fabric", "yarn i/h", "fab inhouse",
        "fabric eta plan", "fabric eta",
    ],
    "in_house_fabric_approval": [
        "fabric in-housed on", "i/b fab appl", "fabric inhouse appl",
    ],
    "pre_production_send": [
        "pps", "pp send", "pps submission", "pre production send", "ppm",
        "program submit on", "pp meeting",
    ],
    "pre_production_approval": [
        "pp appl", "pps appl", "pp approval",
    ],
    "first_pattern": ["first pattern", "fpt"],
    "garment_pattern": [
        "garment pattern", "garment handwork", "garment handwork start",
        "garment handwork end",
    ],
    "planned_completion_date": ["pcd", "planned completion"],
    "size_set": [
        "size set", "sizeset", "sizeset submission", "size-set",
    ],
    # Note: 'SS' (and variants) is intentionally NOT aliased here — it is
    # ambiguous (size_set vs sewing_start) and reliable mapping requires
    # context (look at adjacent 'Cut' or 'Sewing' columns).
    "lot_card": ["lot card", "lotcard"],
    "cutting": [
        "cutting", "cuting", "cut", "cutting start", "cutting complete",
        "cutting end", "cuting start", "cuting end",
    ],
    "feeding": ["feeding", "feed", "feeding start", "feeding end"],
    "sewing": ["sewing"],
    "sewing_start": [
        "sewing start", "knit start", "stitching start", "sewing in",
        "ss start", "ss start plan",
    ],
    "sewing_end": [
        "sewing end", "sewing complete", "knit end", "stitching end",
        "sewing out", "sewing  complete", "ss end", "ss end plan",
    ],
    "final_inspection": [
        "final inspection", "fi", "inspection", "fpt", "fi date",
        "fi plan date",
    ],
    "printing": ["printing", "print"],
    "embroidery": ["embroidery", "emb", "prnt emb", "prnt/emb"],
    "washing": ["washing", "wash"],
    "finishing": [
        "finishing", "finishing start", "finishing complete", "finish",
    ],
    "packing": ["packing", "pack"],
    "ex_factory": [
        "ex factory", "ex factory shipment", "ex-factory", "ex fac",
        "ex con", "shipment",
    ],
    "trims_inhouse": [
        "trims inhouse", "trims in-house", "trim inhouse", "trim ih",
    ],
}


SUBFIELD_VOCAB: dict[str, list[str]] = {
    "planned_date": [
        "plan", "planned", "plan date", "start plan", "end plan",
        "fi plan date", "p", "plan ",
    ],
    "actual_date": [
        "actual", "act", "actl", "action", "start act", "end act", "a",
    ],
    "approval_date": [
        "approval", "approved", "appd", "approved date", "appr",
    ],
    "received_date": [
        "received", "recvd", "rec", "received date", "in",
    ],
    "approved_qty": [
        "approved qty", "appd qty",
    ],
    "quantity": [
        "qty", "quantity",
    ],
    "remarks": [
        "remarks", "remark", "sub", "note", "notes",
    ],
    "comments": [
        "comment", "comments",
    ],
    "deviation_days": [
        "deviation", "dev", "deviation days",
    ],
}


# === Match result =============================================================

@dataclass
class MatchResult:
    canonical: str | None
    score: float
    candidates: list[tuple[str, float]] = field(default_factory=list)


# === helpers ==================================================================

def _norm(s: str) -> str:
    s = str(s).strip().lower()
    # Replace newlines with spaces, normalise punctuation that splits tokens.
    s = re.sub(r"[\n\r\t]+", " ", s)
    s = re.sub(r"[._]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _tokens(s: str) -> set[str]:
    """Lowercase tokens; split on whitespace, slashes, dashes; drop stopwords."""
    s = _norm(s)
    tokens = re.split(r"[\s/\-]+", s)
    stop = {"the", "a", "of", "and", "in", "on", "as", "per", "p.o", "po", "date"}
    return {t for t in tokens if t and t not in stop}


# === Strategy 1: vocab table ==================================================

def _vocab_lookup(vocab: dict[str, list[str]], raw: str) -> MatchResult:
    """Exact-on-alias match (after normalisation)."""
    n = _norm(raw)
    for canonical, aliases in vocab.items():
        if n == canonical:
            return MatchResult(canonical, 1.0, [(canonical, 1.0)])
        for alias in aliases:
            if _norm(alias) == n:
                return MatchResult(canonical, 1.0, [(canonical, 1.0)])
    return MatchResult(None, 0.0, [])


def vocab_field(raw: str, sample_values: list | None = None) -> MatchResult:
    return _vocab_lookup(IDENTITY_VOCAB, raw)


def vocab_stage(raw: str, sample_values: list | None = None) -> MatchResult:
    return _vocab_lookup(STAGE_VOCAB, raw)


def vocab_subfield(raw: str, sample_values: list | None = None) -> MatchResult:
    return _vocab_lookup(SUBFIELD_VOCAB, raw)


# === Strategy 2: rapidfuzz partial / token-set ratio ==========================

def _fuzzy_lookup(
    vocab: dict[str, list[str]], raw: str, threshold: float = 75.0,
) -> MatchResult:
    if fuzz is None:
        return MatchResult(None, 0.0, [])
    n = _norm(raw)
    best_canonical: str | None = None
    best_score = 0.0
    scored: list[tuple[str, float]] = []
    for canonical, aliases in vocab.items():
        candidates = [_norm(canonical.replace("_", " "))] + [_norm(a) for a in aliases]
        score = max(fuzz.WRatio(n, c) for c in candidates)
        scored.append((canonical, score))
        if score > best_score:
            best_score = score
            best_canonical = canonical
    scored.sort(key=lambda x: -x[1])
    if best_score >= threshold:
        return MatchResult(best_canonical, best_score / 100.0, scored[:3])
    return MatchResult(None, best_score / 100.0, scored[:3])


def fuzzy_field(raw: str, sample_values: list | None = None) -> MatchResult:
    return _fuzzy_lookup(IDENTITY_VOCAB, raw)


def fuzzy_stage(raw: str, sample_values: list | None = None) -> MatchResult:
    return _fuzzy_lookup(STAGE_VOCAB, raw)


def fuzzy_subfield(raw: str, sample_values: list | None = None) -> MatchResult:
    return _fuzzy_lookup(SUBFIELD_VOCAB, raw)


# === Strategy 3: token Jaccard ================================================

def _jaccard_lookup(
    vocab: dict[str, list[str]], raw: str, threshold: float = 0.5,
) -> MatchResult:
    raw_tokens = _tokens(raw)
    if not raw_tokens:
        return MatchResult(None, 0.0, [])
    best_canonical: str | None = None
    best_score = 0.0
    scored: list[tuple[str, float]] = []
    for canonical, aliases in vocab.items():
        max_for_canonical = 0.0
        targets = [canonical.replace("_", " ")] + aliases
        for t in targets:
            t_tokens = _tokens(t)
            if not t_tokens:
                continue
            inter = raw_tokens & t_tokens
            union = raw_tokens | t_tokens
            if not union:
                continue
            j = len(inter) / len(union)
            if j > max_for_canonical:
                max_for_canonical = j
        scored.append((canonical, max_for_canonical))
        if max_for_canonical > best_score:
            best_score = max_for_canonical
            best_canonical = canonical
    scored.sort(key=lambda x: -x[1])
    if best_score >= threshold:
        return MatchResult(best_canonical, best_score, scored[:3])
    return MatchResult(None, best_score, scored[:3])


def jaccard_field(raw: str, sample_values: list | None = None) -> MatchResult:
    return _jaccard_lookup(IDENTITY_VOCAB, raw)


def jaccard_stage(raw: str, sample_values: list | None = None) -> MatchResult:
    return _jaccard_lookup(STAGE_VOCAB, raw)


def jaccard_subfield(raw: str, sample_values: list | None = None) -> MatchResult:
    return _jaccard_lookup(SUBFIELD_VOCAB, raw)


# === Strategy 4: sample-value patterns (#6 only) ==============================

_INT_RE = re.compile(r"^\d+$")
_DATE_STR_RE = re.compile(
    r"^\s*(?:\d{1,2}[-/]\w{3}[-/]\d{2,4}|"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s*$",
    re.IGNORECASE,
)


def _classify_sample(v: object) -> str | None:
    """Coarse value classifier.

    Returns one of: 'date', 'int4', 'int_long', 'float', 'short_text',
    'long_text', or None.
    """
    if isinstance(v, (date, datetime)):
        return "date"
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        if 1000 <= v < 100000:
            return "int4"
        return "int_long"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        if _DATE_STR_RE.match(v):
            return "date"
        if _INT_RE.match(v):
            return "int4" if 4 <= len(v) <= 5 else "int_long"
        if len(v) <= 20:
            return "short_text"
        return "long_text"
    return None


def sample_value_field(raw: str, sample_values: list | None = None) -> MatchResult:
    """Infer canonical purely from value patterns. Best used as a secondary signal."""
    if not sample_values:
        return MatchResult(None, 0.0, [])
    classes = [c for c in (_classify_sample(v) for v in sample_values) if c]
    if not classes:
        return MatchResult(None, 0.0, [])
    # Pick the dominant class.
    from collections import Counter
    dominant, count = Counter(classes).most_common(1)[0]
    ratio = count / len(classes)
    if dominant == "date":
        return MatchResult("delivery_date", ratio, [("delivery_date", ratio)])
    if dominant == "int4":
        return MatchResult("io_number", ratio, [("io_number", ratio)])
    if dominant == "int_long":
        return MatchResult("quantity", ratio, [("quantity", ratio)])
    if dominant == "float":
        return MatchResult("price", ratio, [("price", ratio)])
    if dominant in {"long_text"}:
        return MatchResult("style_name", ratio * 0.6, [("style_name", ratio * 0.6)])
    return MatchResult(None, 0.0, [])


# === Strategy 5: combined-weighted ============================================

def _combined_field(raw: str, sample_values: list | None = None) -> MatchResult:
    """Vocab first; fall back to fuzzy; sample-value as tiebreaker / fallback."""
    v = vocab_field(raw)
    if v.canonical is not None:
        return v
    f = fuzzy_field(raw)
    if f.canonical is not None and f.score >= 0.75:
        return f
    s = sample_value_field(raw, sample_values)
    if s.canonical is not None and s.score >= 0.66:
        return s
    return MatchResult(None, max(f.score, s.score), f.candidates)


def _combined_stage(raw: str, sample_values: list | None = None) -> MatchResult:
    v = vocab_stage(raw)
    if v.canonical is not None:
        return v
    f = fuzzy_stage(raw)
    if f.canonical is not None and f.score >= 0.75:
        return f
    j = jaccard_stage(raw)
    if j.canonical is not None and j.score >= 0.5:
        return j
    return MatchResult(None, max(f.score, j.score), f.candidates)


def _combined_subfield(raw: str, sample_values: list | None = None) -> MatchResult:
    v = vocab_subfield(raw)
    if v.canonical is not None:
        return v
    f = fuzzy_subfield(raw)
    if f.canonical is not None and f.score >= 0.75:
        return f
    return MatchResult(None, f.score, f.candidates)


combined_field = _combined_field
combined_stage = _combined_stage
combined_subfield = _combined_subfield


# === Strategy registries ======================================================

FIELD_STRATEGIES: dict[str, Callable[[str, list | None], MatchResult]] = {
    "vocab": vocab_field,
    "fuzzy": fuzzy_field,
    "jaccard": jaccard_field,
    "sample_value": sample_value_field,
    "combined": combined_field,
}

STAGE_STRATEGIES: dict[str, Callable[[str, list | None], MatchResult]] = {
    "vocab": vocab_stage,
    "fuzzy": fuzzy_stage,
    "jaccard": jaccard_stage,
    "combined": combined_stage,
}

SUBFIELD_STRATEGIES: dict[str, Callable[[str, list | None], MatchResult]] = {
    "vocab": vocab_subfield,
    "fuzzy": fuzzy_subfield,
    "combined": combined_subfield,
}
