"""Render an EvalRow list as a console scoreboard (numbers only — no diff)."""
from __future__ import annotations
from evals.runner import EvalRow


def render_matrix(rows: list[EvalRow]) -> str:
    if not rows:
        return "(no eval rows)\n"
    header = (f"{'file':<60} {'pli_rec':>8} {'f_prec':>7} {'f_rec':>7} "
              f"{'stg_rec':>8} {'src':>6} {'hdr':>6} {'sec':>6}")
    sep = "-" * len(header)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"{r.file_name[:60]:<60} {r.pli_recall:>8.3f} {r.field_precision:>7.3f} "
            f"{r.field_recall:>7.3f} {r.stage_recall:>8.3f} "
            f"{r.source_cell_match:>6.3f} {r.header_match:>6.3f} "
            f"{r.duration_seconds:>6.1f}"
        )
    if rows:
        avg = lambda f: sum(getattr(r, f) for r in rows) / len(rows)
        lines.append(sep)
        lines.append(
            f"{'AVERAGE':<60} {avg('pli_recall'):>8.3f} "
            f"{avg('field_precision'):>7.3f} {avg('field_recall'):>7.3f} "
            f"{avg('stage_recall'):>8.3f} {avg('source_cell_match'):>6.3f} "
            f"{avg('header_match'):>6.3f} {avg('duration_seconds'):>6.1f}"
        )
    return "\n".join(lines) + "\n"
