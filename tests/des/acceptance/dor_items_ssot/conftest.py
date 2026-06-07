"""pytest-bdd configuration for the dor-items-ssot suite.

DISTILL-authored RED scaffold (ADR-025 + ADR-028): every scenario in the
slice-01 ``.feature`` file is authored ahead of the implementation. The
composition root (``steps/composition.py``) drives the PRODUCTION ``des
dor-items`` reader subcommand end-to-end through the real ``des`` single entry
point (``des.cli.__main__``) as a subprocess (Mandate-13 driving-port-only,
Layer 3 subprocess), against the real repo-tracked ``nWave/data/dor-items.yaml``
SSOT.

The suite COLLECTS cleanly (the composition imports only test-local types plus
stdlib ``subprocess``/``json``), and each scenario RED-fails for the RIGHT
reason when unskipped (MISSING_FUNCTIONALITY): ``dor-items`` is not yet a
registered subcommand of the ``des`` dispatcher and ``nWave/data/dor-items.yaml``
does not yet exist, so ``des dor-items ...`` errors with an unknown-subcommand
(non-zero exit) and emits no item lines. The reader surfaces an EMPTY canonical
set, and each Then fails with a semantic ``AssertionError`` (missing nine items
/ missing Outcome-KPIs item / missing separate hard gate), never a collection /
import / setup error (pre-DELIVER fail-for-right-reason gate).

DELIVER's RED phase removes the per-scenario ``@skip`` tags one slice at a time
per the one-at-a-time TDD cadence, then ships ``nWave/data/dor-items.yaml`` +
the ``des.cli.dor_items`` reader registered in the ``__main__`` dispatcher to
GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the skip hook is scoped to items collected from
# under here so a session-wide ``@slice-NN`` / ``@skip`` keyword match never
# poisons unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Author-ahead RED-scaffold marker tags. A scenario carrying ANY of these is
# skipped until DELIVER unskips it (ADR-028 RED scaffold: collects, does not
# run-green). DELIVER removes the ``@skip``/``@pending`` tags from the
# ``.feature`` file at the RED phase.
_SKIPPED_TAGS: frozenset[str] = frozenset({"skip", "pending"})


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip every author-ahead RED-scaffold scenario until DELIVER unskips it."""
    skip_marker = pytest.mark.skip(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation"
    )
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        if set(item.keywords) & _SKIPPED_TAGS:
            item.add_marker(skip_marker)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
