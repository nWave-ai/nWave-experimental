#!/usr/bin/env python3
"""Render an nWave markdown document to a self-contained HTML page.

A THIN DRIVER, and nothing else. The renderer itself moved to
``des.adapters.driven.rendering.nwave_document`` when it gained a second caller
that must work from an installed wheel (``des project``). ``scripts/`` does not
ship, so leaving the implementation here would have made the shipped projection
work only in a dev checkout. This file keeps the command name every existing
caller and document already uses.
"""

from __future__ import annotations

import sys
from pathlib import Path


# The worktree's own src/ must win over any installed projection, for the reason
# scripts/docgen.py states: an editable environment may append a stale root.
_src = str(Path(__file__).resolve().parent.parent / "src")
if Path(_src).is_dir():
    if _src in sys.path:
        sys.path.remove(_src)
    sys.path.insert(0, _src)

from des.adapters.driven.rendering.nwave_document import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
