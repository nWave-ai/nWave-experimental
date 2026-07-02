"""Shared pytest-bdd fixture + helper for opt-in-per-step-double-review acceptance steps.

Mirrors the SHAPE of `tests/des/acceptance/rigor_review_step_toggles/steps/conftest.py`
(the sibling, shipped/sealed feature this one extends) rather than importing it
cross-package -- the sibling itself established the per-feature self-contained
convention (each slice module there duplicated the identical fixture/helper
inline until its own feature-end consolidation). A fresh, local `ctx` fixture +
`_write_project_config` helper keeps this feature independent of the sibling's
internal module layout while reusing the exact proven pattern (Test Reuse
Analysis: EXTEND-by-pattern-reuse, not by import).

``ctx`` is a pytest fixture -- auto-discovered by every step module under this
directory, no import needed. ``_write_project_config`` is a plain helper, so
each step module imports it explicitly (``from .conftest import
_write_project_config``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Mutable context shared across Given/When/Then steps in a scenario."""
    return {}


def _write_project_config(tmp_path: Path, rigor: dict[str, Any]) -> Path:
    """Write a real project ``.nwave/des-config.json`` and return its path."""
    nwave_dir = tmp_path / "project" / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    config_path = nwave_dir / "des-config.json"
    config_path.write_text(json.dumps({"rigor": rigor}), encoding="utf-8")
    return config_path
