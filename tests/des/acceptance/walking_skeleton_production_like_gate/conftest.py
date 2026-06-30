"""pytest-bdd configuration for the walking-skeleton-production-like-gate suite.

DISTILL-authored RED scaffold (ADR-025): every scenario in the sixteen
carpaccio slice `.feature` files is authored ahead of the implementation. The
composition root (`steps/composition.py`) imports the production CLIs
`des.cli.walking_skeleton_gate` / `walking_skeleton_done_gate`, which DISTILL
ships as RED scaffolds whose service methods raise `AssertionError`. Imports
succeed (no BROKEN classification); every scenario reds for the RIGHT reason --
missing functionality.

The 16 carpaccio slices re-decompose DESIGN's 9-slice plan to the
`atdd_pure.carpaccio_slice_max: 3` ceiling (each carpaccio slice <= 3
`@slice-NN`-tagged scenario blocks). slice-01 is the `@walking-skeleton
@wiring_e2e` vertical.

The collection hook below marks every scenario `xfail(strict=True)` until
DELIVER greens it. DELIVER removes this hook (or narrows it slice-by-slice) at
the GREEN phase, one slice at a time, per the one-at-a-time TDD cadence.

To enable a single slice for DELIVER, narrow `_RED_SCAFFOLD_SLICES` to exclude
that slice's tag, or delete the hook once all slices are green.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here. `pytest_collection_modifyitems` runs session-wide on EVERY
# collected item; without this scope the `slice-NN` keyword match would also
# xfail unrelated suites that happen to tag their own scenarios `@slice-NN`
# (e.g. atdd_pure_spine_hardening), poisoning a whole-`tests/des/` run.
_SUITE_DIR = Path(__file__).parent


# Slices still RED (author-ahead). DELIVER removes a tag as its slice greens.
# slice-01 (the @walking-skeleton @wiring_e2e vertical) is NOT in the RED set:
# an earlier abandoned classic-attempt commit (c631692f5) shipped a working
# slice-01 production implementation, so the slice-01 ATs are genuinely GREEN
# already. DELIVER reconciles that pre-existing code against this DISTILL
# contract; slices 02-16 are author-ahead RED scaffolds.
# Empty under F-CONSOLIDATION-FUTURE-SLICE-CANON (ratified A, future-absent):
# advanced slices 03-16 removed off disk (deferred to backlog, re-authored JIT
# per the canonical sequence). Only delivered cores slice-01/02 remain — no
# author-ahead RED scaffold to xfail.
_RED_SCAFFOLD_SLICES = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail(strict) until GREEN."""
    xfail = pytest.mark.xfail(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation",
        strict=True,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        keywords = set(item.keywords)
        if keywords & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
