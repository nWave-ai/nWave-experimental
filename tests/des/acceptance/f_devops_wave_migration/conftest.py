"""Shared fixtures for f-devops-wave-migration ATs.

The `devops_wave_migration_steps` package name is deliberately UNIQUE tree-wide
(S1 step-text/namespace uniqueness): other acceptance feature trees prepend their
own feature root onto sys.path, so a generic `gate_steps` or `steps` package
would collide by NAME under whole-tree collect (pytest prepend importmode) and
shadow this feature's `domain_types`/`composition` — or be shadowed BY them —
across the session. `devops_wave_migration_steps` cannot collide with any existing
test step-package (grep-verified at authoring; sibling `distill_wave_migration`
uses `distill_gate_steps`).

`composition` is function-scoped on `tmp_path` so each scenario authors its own
manifest in isolation; the SUT it drives is always the REAL production port (the
real `des skill-normative-gate` dispatcher subprocess) over the REAL shipped
nw-platform-architect / nw-devops / nw-infrastructure-and-observability prose —
only the manifest JSON is tmp_path-scoped.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_FEATURE_ROOT = Path(__file__).resolve().parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from devops_wave_migration_steps.composition import (
    DevopsWaveMigrationComposition,
)


@pytest.fixture()
def composition(tmp_path) -> DevopsWaveMigrationComposition:
    """A fresh composition root per scenario, isolated under tmp_path."""
    return DevopsWaveMigrationComposition(tmp_path)


@pytest.fixture()
def state() -> dict:
    """Per-scenario mutable state bag (before/after snapshots for state_delta)."""
    return {}
