#!/usr/bin/env python3
"""Thin shim -- the real implementation now lives under ``src/des/``.

Relocated to ``src/des/domain/gate_ratchet.py`` (gate-ratchet-skill-normative,
Mikado D86): a SECOND gate (``des skill-normative-gate``) needed to reuse this
gate-agnostic decision, and ``src/des/`` cannot import ``scripts/`` (dev-only,
not shipped). This file exists ONLY so
``python3 scripts/validation/validate_mikado_tree_coherence.py`` and the
``mikado-tree-coherence`` pre-commit hook keep working byte-identically -- do
not add logic here, edit the real module instead.
"""

from __future__ import annotations

import sys
from pathlib import Path


_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from des.domain.gate_ratchet import (  # noqa: E402
    RatchetDecision,
    RatchetOutcome,
    decide_ratchet,
    undecidable_baseline,
)


__all__ = [
    "RatchetDecision",
    "RatchetOutcome",
    "decide_ratchet",
    "undecidable_baseline",
]
