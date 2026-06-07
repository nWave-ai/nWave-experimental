"""pytest-bdd configuration for the classic-spine-decommission suite.

DISTILL-authored RED scaffold (ADR-025): every scenario in the seven slice
`.feature` files is authored ahead of the implementation. The composition root
(`steps/composition.py`) and the production CLIs it drives
(`des.cli.classify_features`, `des.cli.convert_to_atdd_pure`) are shipped as
RED scaffolds whose entry points raise `AssertionError` -- so every scenario
reds for the RIGHT reason (missing functionality), never `ImportError`.

The collection hook below marks every author-ahead scenario `xfail(strict=True)`
until DELIVER greens it. DELIVER narrows `_RED_SCAFFOLD_SLICES` slice-by-slice
at the GREEN phase, one slice at a time, per the one-at-a-time TDD cadence.

slice-01 (the walking skeleton) and slice-02 (F-13, the hard prerequisite) are
greened first; the remaining slices follow in dependency order.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected from
# under here so the `slice-NN` keyword match cannot poison unrelated suites
# (e.g. walking_skeleton_production_like_gate also tags `@slice-NN`).
_SUITE_DIR = Path(__file__).parent


# Slices still RED (author-ahead). DELIVER removes a tag as its slice greens.
# slice-01 (walking skeleton) and slice-02 (F-13) are the first to green.
#
# slice-15 (feature-end-review gap slice, D1 + D2-Step-3) was greened by the
# feature-end-fix crafter pass; no slices remain RED.
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN.

    `strict=False`: a Scenario Outline in a still-RED slice may share an example
    row with an already-greened slice (e.g. slice-03's per-class outline shares
    the `classic-mid-implementation` row with slice-01's walking skeleton). Such
    a row legitimately XPASSes once its overlapping slice greens -- a non-strict
    xfail reports the XPASS without failing the build, while still flagging the
    remaining genuinely-RED scaffolds.
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
