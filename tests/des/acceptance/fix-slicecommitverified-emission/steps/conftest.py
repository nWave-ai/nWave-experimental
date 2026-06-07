"""Shared pytest-fixture SSOT for the fix-slicecommitverified-emission ATs.

The `composition` (production-wired entry-gate composition rooted at a real
tmp git repo) and `outcome_box` (When -> Then carrier) fixtures are the SINGLE
SOURCE for both slice-01 (`test_auto_backfill_entry_gate.py`) and slice-02
(`test_fail_closed_entry_gate.py`). pytest resolves conftest fixtures for every
test module on the path -- one definition, zero duplication across slices.

Step definitions are NOT placed here: pytest-bdd binds `@given/@when/@then`
bodies to the test module where `scenarios()` is declared, so each slice module
declares its own step literals (every literal unique within the feature dir --
S1 Tier-2 gate). The shared SSOT for behaviour is `BackfillEntryGateComposition`
methods the step bodies delegate to (Pillar 2 via shared service vocabulary).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .composition import BackfillEntryGateComposition, EntryGateOutcome


@pytest.fixture
def composition(tmp_path: Path) -> BackfillEntryGateComposition:
    """Production-wired entry-gate composition rooted at a real tmp git repo."""
    comp = BackfillEntryGateComposition(tmp_path)
    comp.init_repo()
    return comp


@pytest.fixture
def outcome_box() -> dict[str, EntryGateOutcome]:
    """Carrier for the entry-gate outcome across When -> Then."""
    return {}
