"""Judge gating components — route ambiguous findings to judge agents.

Pipelines never import judge agents directly. Each gate component
owns its agent privately, decides when to invoke it, and applies the
verdict to the surrounding findings list. This is the boundary that
keeps agent calls observable, swappable, and testable in isolation
from pipeline wiring.
"""
