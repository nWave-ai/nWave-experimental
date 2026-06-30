"""Conftest for mode-registry-single-locus acceptance tests.

One composition fixture per slice; slice-01 ships
`ModeRegistryResolutionComposition` (see its module docstring for the
Pillar-3 / Driving-Port-Only Boundary / Dormant-Seam attestations).

Feature-specific package naming (`steps/` under this feature dir, step
literals phrased for this feature only) preserves the S1 step-text uniqueness
invariant across the acceptance suite (friction #56 standing).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .steps.composition_slice_01 import ModeRegistryResolutionComposition
from .steps.composition_slice_02 import DocgenProjectionComposition
from .steps.composition_slice_03 import CatalogFrontmatterProjectionComposition
from .steps.composition_slice_04 import BulkMigrationSweepComposition
from .steps.composition_slice_05 import GuardrailGateComposition


@pytest.fixture
def composition(tmp_path: Path) -> ModeRegistryResolutionComposition:
    """The single composition-root service all slice-01 step methods delegate to."""
    return ModeRegistryResolutionComposition(tmp_path)


@pytest.fixture
def projection_composition(tmp_path: Path) -> DocgenProjectionComposition:
    """The single composition-root service all slice-02 step methods delegate to."""
    return DocgenProjectionComposition(tmp_path)


@pytest.fixture
def frontmatter_composition(tmp_path: Path) -> CatalogFrontmatterProjectionComposition:
    """The single composition-root service all slice-03 step methods delegate to."""
    return CatalogFrontmatterProjectionComposition(tmp_path)


@pytest.fixture
def bulk_composition(tmp_path: Path) -> BulkMigrationSweepComposition:
    """The single composition-root service all slice-04 step methods delegate to."""
    return BulkMigrationSweepComposition(tmp_path)


@pytest.fixture
def guardrail_composition(tmp_path: Path) -> GuardrailGateComposition:
    """The single composition-root service all slice-05 step methods delegate to."""
    return GuardrailGateComposition(tmp_path)
