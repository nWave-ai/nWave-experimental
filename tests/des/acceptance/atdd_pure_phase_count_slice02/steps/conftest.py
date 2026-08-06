"""Pytest-bdd fixtures for the atdd_pure_phase_count slice-02 acceptance steps."""

from __future__ import annotations

import pytest

from .composition import PhaseResolveComposition


@pytest.fixture
def phase_resolver() -> PhaseResolveComposition:
    return PhaseResolveComposition()
