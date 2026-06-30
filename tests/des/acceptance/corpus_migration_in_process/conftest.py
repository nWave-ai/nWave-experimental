"""Shared composition fixture for the f-test-corpus-migration-in-process ATs.

The production-wired composition root (driving-port-only, Mandate-13) is shared
across the three slice-01 step modules. It drives the REAL per-site seams
IN-PROCESS; the ONE legitimate fork (the scorecard @walking_skeleton wiring proof)
lives in its own WS step module, never here.
"""

from __future__ import annotations

import pytest

from .steps.composition import CorpusMigrationComposition


@pytest.fixture
def composition() -> CorpusMigrationComposition:
    """Production-wired composition root driving the real per-site seams in-process."""
    return CorpusMigrationComposition()
