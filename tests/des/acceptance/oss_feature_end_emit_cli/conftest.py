"""pytest-bdd configuration for the oss-feature-end-emit-cli suite.

DISTILL-authored RED scaffold (ADR-025 + ADR-028): every scenario in the
slice-01 ``.feature`` file is authored ahead of the implementation. The
composition root (``steps/composition.py``) drives the PRODUCTION
``des emit-feature-end`` subcommand end-to-end through the real ``des`` single
entry point (``des.cli.__main__``) as a subprocess (Mandate-13 driving-port-
only, Layer 3 subprocess), against a real git working tree and a real
AT-completion ledger. No production module is imported-and-called at the step
boundary: the CLI is invoked as a subprocess and the ledger substrate is read
through the production ``AtCompletionLedger`` reader (observable read-back,
NOT the SUT).

The suite therefore COLLECTS cleanly (the composition imports only test-local
types plus the already-shipped ``AtCompletionLedger``), and each scenario
RED-fails for the RIGHT reason when unskipped (MISSING_FUNCTIONALITY):

  * ``emit-feature-end`` is not yet a registered subcommand of the ``des``
    dispatcher, so ``des emit-feature-end ...`` errors with an unknown-
    subcommand (non-zero exit) and appends NO record. AT-1/AT-2 then fail
    because the success outcome / read-back record / bound hash is absent;
    AT-3 (the anti-theater refusal) is the one scenario whose REFUSED outcome
    a missing subcommand vacuously satisfies, but it ALSO asserts the ledger
    carries no verdict record AND -- once the subcommand exists -- that the
    refusal is the CLI's bound-hash check, not a dispatcher miss. Every case
    is a semantic ``AssertionError`` (or a non-zero exit the outcome maps to),
    never a collection / import / setup error (pre-DELIVER fail-for-right-
    reason gate).

DELIVER's RED phase removes the file-head ``@skip``/``@pending`` tags one
slice at a time per the one-at-a-time TDD cadence, then implements the
``des.cli.emit_feature_end`` module (thin over
``AtCompletionLedger.append_feature_end_event``) and registers it in the
``__main__`` dispatcher registry + the gate catalog (the 1:1 mirror, slice-04
AD-26 lesson) to GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the skip hook is scoped to items collected from
# under here so a session-wide `@slice-NN` / `@skip` keyword match never
# poisons unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Author-ahead RED-scaffold marker tags. A scenario carrying ANY of these is
# skipped until DELIVER unskips it (ADR-028 RED scaffold: collects, does not
# run-green). DELIVER removes the `@skip`/`@pending` tags from the `.feature`
# file head at the RED phase.
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
