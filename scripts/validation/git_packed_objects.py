#!/usr/bin/env python3
"""Thin shim -- the real implementation now lives under ``src/des/``.

Relocated to ``src/des/adapters/driven/git/git_packed_objects.py``
(gate-ratchet-skill-normative, Mikado D86): ``src/des/`` production code (the
skill-normative gate's ratchet baseline) needed to reuse this reader, and
``src/des/`` cannot import ``scripts/`` (dev-only, not shipped). This file
exists ONLY so ``python3 scripts/validation/validate_mikado_tree_coherence.py``
and the ``mikado-tree-coherence`` pre-commit hook keep working
byte-identically -- do not add logic here, edit the real module instead.
"""

from __future__ import annotations

import sys
from pathlib import Path


_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from des.adapters.driven.git.git_packed_objects import (  # noqa: E402
    PackedObjectStore,
)


__all__ = ["PackedObjectStore"]
