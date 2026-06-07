"""pytest-bdd configuration for the oss-hook-side-phase-injection suite.

DISTILL-authored RED scaffold (ADR-025 + ADR-028): every scenario in the
slice-01 ``.feature`` file is authored ahead of the implementation. The
composition root (``steps/composition.py``) drives the PRODUCTION
``handle_subagent_stop`` hook end-to-end through its real JSON stdin protocol
as a subprocess (Mandate-13 driving-port-only, Layer 3/4 wiring_e2e), against a
real git repo carrying a real feature-delta ``[REF] Slice Plan`` and a real
AT-completion ledger. No production module is imported-and-called at the step
boundary: the hook is invoked as a subprocess and the ledger substrate is
seeded/read through the production ``AtCompletionLedger`` writer (precondition
state + observable read-back, NOT the SUT).

The suite therefore COLLECTS cleanly (the composition imports only test-local
types plus the already-shipped ``AtCompletionLedger``), and each scenario
RED-fails for the RIGHT reason when unskipped:

  * ``D_DISTILL`` is not yet a member of the ``ATDDPurePhase`` closed-world enum
    and the handler has no ``_handle_distill_exit_gate`` branch, so a
    ``D_DISTILL`` return parses to ``atdd_pure_phase=None`` and falls through to
    the generic atdd_pure handler, which ALLOWS without emitting any phase
    event. AT-1 then fails because no ``WorkflowPhaseCompletedDistill`` record
    is read back; AT-2/AT-3 fail because the gate ALLOWS where a BLOCK was
    expected -- a semantic ``AssertionError`` in every case, never a collection
    / import / setup error (pre-DELIVER fail-for-right-reason gate).

The collection hook below SKIPS every ``@skip``-tagged scenario so the file
collects but does not run-green yet. DELIVER's RED phase removes the file-head
``@skip @pending`` tags one slice at a time per the one-at-a-time TDD cadence,
then implements the three coupled production edits (``D_DISTILL`` into the enum
+ ``_FEATURE_END_PHASES``, ``append_workflow_phase_completed``, the
``_handle_distill_exit_gate`` branch) to GREEN.
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
