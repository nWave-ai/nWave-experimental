"""Shared fixtures for skill-normative-content-gate ATs.

The `gate_steps` package name is deliberately distinct from a bare `steps/`
(S1 step-text/namespace uniqueness): other acceptance feature trees prepend
their own feature root onto sys.path, and a generic `steps` package would
shadow this feature's `domain_types`/`composition` across the session.

`composition` is function-scoped on `tmp_path` so each scenario authors its own
manifest/fixtures in isolation; the SUT it drives is always the real production
port (real `des` dispatcher / real `pre_write` handler) — only the manifest and
the mutated-skill copies are tmp_path-scoped.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_FEATURE_ROOT = Path(__file__).resolve().parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from gate_steps.composition import SkillNormativeGateComposition


@pytest.fixture()
def composition(tmp_path) -> SkillNormativeGateComposition:
    """A fresh composition root per scenario, isolated under tmp_path."""
    return SkillNormativeGateComposition(tmp_path)


@pytest.fixture()
def state() -> dict:
    """Per-scenario mutable state bag (before/after snapshots for state_delta)."""
    return {}
