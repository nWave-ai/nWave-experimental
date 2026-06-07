"""pytest-bdd configuration for the oss-earned-verdict-gate suite.

DISTILL-authored RED scaffold (ADR-025 + ADR-028): every scenario in the
slice-01 ``.feature`` file is authored ahead of the implementation. The
composition root (``steps/composition.py``) drives the production
``earned-verdict`` CLI via a ``python -m des.cli.earned_verdict`` subprocess --
a module DELIVER has not created yet. The suite therefore COLLECTS cleanly (no
ImportError -- the composition imports only test-local types), and each
scenario RED-fails for the RIGHT reason when unskipped: the CLI subprocess
exits non-zero / emits no envelope -> the schema + status Then steps fail with
a semantic AssertionError, not a setup error (pre-DELIVER
fail-for-right-reason gate).

The collection hook below SKIPS every ``@skip``-tagged scenario so the file
collects but does not run-green yet. DELIVER's RED phase removes the file-head
``@skip @pending`` tags (or narrows ``_SKIPPED_TAGS``) one slice at a time per
the one-at-a-time TDD cadence, then implements the CORE + CLI to GREEN.
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
