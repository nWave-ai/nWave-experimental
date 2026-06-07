"""pytest-bdd configuration for the fix-oss-environmental-e2e-gate suite.

DISTILL-authored RED scaffold (ADR-025): every scenario in the four carpaccio
slice `.feature` files is authored ahead of the implementation. The
composition root (`steps/composition.py`) imports the production CLI
`des.cli.verify_environmental_e2e`, which DISTILL ships as a RED scaffold whose
service methods raise `AssertionError`. Imports succeed (no BROKEN
classification); every scenario reds for the RIGHT reason -- missing
functionality.

CONTRACT SOURCE: the suite is authored against the NORMATIVE-FROZEN L1.4
contract (`docs/architecture/methodology/gate-family-implementation-2026-05-21.md`
section L1.4, v5) -- the single SSOT for the `verify_environmental_e2e`
cross-tree contract. The feature-delta's pre-freeze CLI spec diverges; L1.4
governs (see the DISTILL report's L1.4 divergence section).

The collection hook below marks every scenario `xfail(strict=True)` until
DELIVER greens it. DELIVER narrows `_RED_SCAFFOLD_SLICES` slice-by-slice at the
GREEN phase, one slice at a time, per the one-at-a-time TDD cadence.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here so a session-wide `@slice-NN` keyword match never poisons
# unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Every slice is author-ahead RED until DELIVER greens it. DELIVER removes a
# tag from this set as its slice greens. All four slices now green -- the set
# is empty; the suite has no remaining xfail RED scaffolds.
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN.

    `strict=False` — a slice-03 Scenario Outline shares 2 rows with slice-01's
    situations (`green`/`red`); slice-01's GREEN organically lifts those rows
    to PASS. Strict xfail would treat the XPASS as a regression. The cadence
    intent ("RED until DELIVER greens this slice") is preserved by the xfail
    marker; strictness is dropped to accommodate shared-substrate row-lifting
    across slices.
    """
    xfail = pytest.mark.xfail(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation",
        strict=False,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    # Parallel-load pinning: this suite runs cwd=<real repo> environmental
    # e2e subprocesses / real-tree scans over the AtCompletionLedger
    # substrate. Pin every item to one xdist worker group so the contract
    # gate's `-n auto --dist loadgroup` cannot race them across workers
    # (NOT masking -- they run honestly, serialized within one worker).
    scan_group = pytest.mark.xdist_group("real_repo_scan")
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        item.add_marker(scan_group)
        if set(item.keywords) & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
