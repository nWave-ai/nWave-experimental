"""Shared pytest-bdd fixture + helper for rigor-review-step-toggles acceptance steps.

Feature-end whole-feature refactor (ADR-028 D6 E_BATCH_REFACTOR): extracted from
the byte-identical inline copies that shipped in every per-slice step module
(slices 01-06). Each slice deliberately mirrored the ``ctx`` fixture and the
``_write_project_config`` helper inline to stay self-contained mid-feature (see
each slice's "Self-contained per the sustainability analysis" docstring note,
which explicitly deferred this consolidation to feature-end). Now that the
feature is fully delivered, the duplication is consolidated here.

``ctx`` is a pytest fixture -- auto-discovered by every step module under this
directory, no import needed. ``_write_project_config`` is a plain helper, so
each step module imports it explicitly (``from .conftest import
_write_project_config``).

Per-slice ``@given``/``@when``/``@then`` step-definition bodies stay in their
own modules, unconsolidated: several diverge in assertion-guidance text
(e.g. slice-06's membership ``Then`` carries extra DELIVER-target guidance that
slices 01/03/04 do not), and pytest-bdd resolves duplicate-text steps via the
calling module's fixture closure -- moving only a SUBSET of the identical-text
steps here without auditing every divergence risks an ambiguous-step-binding
or a silent behavior change. The fixture/helper layer is the safe, verified
DRY win; further step consolidation is deferred.
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
