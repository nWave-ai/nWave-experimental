"""pytest-bdd configuration for the fix-robustness-pbt-density-gate suite.

DISTILL-authored RED scaffold (ADR-025): every scenario in the carpaccio
slice `.feature` files is authored ahead of the implementation. The
composition root (`steps/composition.py`) RED-scaffolds the production CLI
`scripts.cli.check_robustness_density` -- its service methods raise
`AssertionError`. Imports succeed (no BROKEN classification); every scenario
reds for the RIGHT reason -- missing functionality.

The collection hook below marks every scenario whose tag set intersects
`_RED_SCAFFOLD_SLICES` with `xfail(strict=False)` until DELIVER greens it.
DELIVER narrows the set slice-by-slice at the GREEN phase, one slice at a
time, per the one-at-a-time TDD cadence.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here so a session-wide `@slice-NN` keyword match never poisons
# unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Every slice is author-ahead RED until DELIVER greens it. DELIVER removes a
# tag from this set as its slice greens. slice-01 greened by DELIVER on
# 2026-05-23 (walking-skeleton CLI shipped at scripts/cli/check_robustness_density.py).
# slice-02 greened by DELIVER M65 on 2026-05-25 (empty-declaration guard +
# DECISION D1 provenance check shipped via stdout diagnostic tokens).
# slice-03 greened by DELIVER M68 on 2026-05-25 (genuineness layers 1+3 +
# adversarial-AST robustness probe shipped: RobustnessPBTShallow / RobustnessAdvisoryUnclassified).
# slice-04 greened by DELIVER on 2026-05-26 (layer-2 mutmut-delta proxy +
# R5 three-state classifier shipped: RobustnessPBTNotFalsifiable /
# RobustnessLayer2Unavailable + new exit code 3 UNAVAILABLE).
# slice-05 greened by DELIVER on 2026-05-27 (wiring slice: at_review_verdict
# consumes check_robustness_density exit code via --robustness-declaration /
# --robustness-at-scope args; SubagentStop hook intercept
# scripts/hooks/subagent_stop_robustness_gate.py registered; framework-catalog
# quality_gates: robustness-pbt-density-gate entry added; RobustnessCoverageMiss
# stdout token emitted on slice-01 coverage-miss path for downstream wiring).
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN.

    `strict=False` -- a later-slice Scenario Outline may share situations with
    an earlier slice's situations; an earlier slice's GREEN organically lifts
    those rows to PASS. Strict xfail would treat the XPASS as a regression.
    The cadence intent ("RED until DELIVER greens this slice") is preserved by
    the xfail marker; strictness is dropped to accommodate shared-substrate
    row-lifting across slices.
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
