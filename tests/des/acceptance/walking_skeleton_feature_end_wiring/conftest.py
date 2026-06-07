"""pytest-bdd configuration for the fix-walking-skeleton-feature-end-wiring suite.

DISTILL-authored RED scaffold (ADR-025): the slice's `.feature` is authored
ahead of the production wiring extension. The production U4 enforcer
(`_missing_feature_end_cycle_records`) and the verify_deliver_integrity CLI
mirror import successfully (no BROKEN classification), but their
`_REQUIRED_FEATURE_END_RECORDS` frozenset does NOT YET include
`WalkingSkeletonGateRan` and the union read does NOT YET include
`walking_skeleton_events()`. Every scenario reds for the RIGHT reason --
MISSING_FUNCTIONALITY (production behaviour absent), not ImportError /
FixtureBroken / SetupFailure (Pre-DELIVER fail-for-right-reason gate).

The collection hook below marks every slice-01 scenario `xfail(strict=True)`
until DELIVER greens it. DELIVER narrows `_RED_SCAFFOLD_SLICES` slice-by-slice
at the GREEN phase, one slice at a time, per the one-at-a-time TDD cadence.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here so a session-wide `@slice-NN` keyword match never poisons
# unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Every slice is author-ahead RED until DELIVER greens it. DELIVER removes a
# tag from this set as its slice greens.
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN.

    `strict=False` -- the slice-01 Outline includes a row whose contract
    holds invariantly both pre- and post-wiring (the heartbeat-present case
    where the missing-record set is `{}` for the walking-skeleton heartbeat
    REGARDLESS of whether the frozenset includes it -- absent and not-yet-
    looked-for are observationally identical). Similarly the regression-pin
    scenario (AT-3, with-heartbeat case) seeds the heartbeat so the
    missing-record set is empty pre-extension too. Strict xfail would treat
    these organic-PASS rows as XPASS-regressions; mirrors the
    `fix_oss_environmental_e2e_gate` slice-03 pattern. The RED cadence intent
    is preserved by the marker; the genuine RED rows (heartbeat-missing
    Outline row + CLI parity scenario) fail organically today and will be
    lifted by DELIVER's frozenset+union extension.
    """
    xfail = pytest.mark.xfail(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation",
        strict=False,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        if set(item.keywords) & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
