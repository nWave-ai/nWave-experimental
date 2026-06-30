"""Shared pytest-fixture SSOT for the des-e2-contract-gate-degrade-loud ATs.

The ``composition`` (production-wired degrade-loud composition rooted at a real
tmp git repo) and ``outcome_box`` (When -> Then carrier) fixtures are the
SINGLE source for the slice-01 step module. pytest resolves conftest fixtures
for every test module on the path -- one definition, zero duplication.

Step definitions are NOT placed here: pytest-bdd binds ``@given/@when/@then``
bodies to the test module where ``scenarios()`` is declared. The behavioural
SSOT is ``DegradeLoudComposition`` methods the step bodies delegate to
(Pillar 2 via shared service vocabulary, not shared decorator strings).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .composition import DegradeLoudComposition, EntryGateOutcome


@pytest.fixture
def composition(tmp_path: Path) -> DegradeLoudComposition:
    """Production-wired degrade-loud composition rooted at a real tmp git repo."""
    comp = DegradeLoudComposition(tmp_path)
    comp.init_repo()
    return comp


@pytest.fixture
def outcome_box() -> dict[str, EntryGateOutcome]:
    """Carrier for the in-order guard outcome across When -> Then."""
    return {}
