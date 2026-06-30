"""pytest-bdd configuration for the ws-gate-manifest-optional suite.

DISTILL-authored per-slice (ADR-025 + ADR-028, atdd_pure per-slice JIT). slice-01
is the ENTERING slice: its scenarios are NOT skipped. Three of them (AC-1/2/3)
RED-fail against HEAD for the right reason -- the floor fail-closes (usage exit 2)
the moment the manifest is absent, so the certify/refuse/refuse-to-decide
assertions fail with a semantic AssertionError (observed verdict is the usage
fail-close, not the expected NA/FAIL/INDETERMINATE). AC-4 (manifest present) is a
live-green preservation guard -- the explicit-manifest path already behaves.

The composition root (`steps/composition_manifest_optional.py`) drives the
PRODUCTION `des walking-skeleton-gate` command end-to-end through the real `des`
single entry point (`des.cli.__main__`) as a subprocess (Mandate-13
driving-port-only, Layer 3 subprocess), against a real staged feature directory on
a real (synthetic) git work-tree. No production module is imported and called at
the step boundary -- the CLI is invoked as a subprocess and the verdict is read
back from the command's printed JSON (observable read-back, NOT the SUT). The
suite therefore COLLECTS cleanly (the composition imports only test-local types
plus the shared `tests.env_parity` helper -- zero `des.*` imports).

A future slice's `.feature` file would be authored JIT when that slice enters
DELIVER; its scenarios -- when present -- would carry an author-ahead
`@skip`/`@pending` tag this hook honours. slice-01 carries no such tag, so the
hook leaves every scenario runnable.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the skip hook is scoped to items collected from
# under here so a session-wide keyword match never poisons unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Author-ahead RED-scaffold marker tags for FUTURE slices. A scenario carrying
# ANY of these is skipped until DELIVER unskips it. slice-01 (the entering slice)
# carries none -- every scenario runs now.
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
