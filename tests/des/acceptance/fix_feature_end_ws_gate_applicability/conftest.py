"""pytest-bdd configuration for the fix-feature-end-ws-gate-applicability suite.

DISTILL-authored per-slice (ADR-025 + ADR-028, atdd_pure per-slice JIT). slice-01
is the ENTERING slice (the walking skeleton): its scenarios are NOT skipped --
they RED-fail against HEAD for the right reason (the diagnostic filter does not
exist yet, so the cycle reports the `des.runtime.freshness.autoskipped` notice
instead of the gate's real reason), then GREEN once A_GREEN ships
`_strip_runtime_event_lines`.

The composition root (`steps/composition.py`) drives the PRODUCTION
`des feature-end run` command end-to-end through the real `des` single entry
point (`des.cli.__main__`) as a subprocess (Mandate-13 driving-port-only, Layer 3
subprocess), against a real staged feature directory on a real (synthetic)
developer checkout. No production module is imported and called at the step
boundary -- the CLI is invoked as a subprocess and the refusal reason is read
back from the command's printed JSON (observable read-back, NOT the SUT).

The suite therefore COLLECTS cleanly (the composition imports only test-local
types plus the shared `tests.env_parity` helper -- zero `des.*` imports), and
each scenario RED-fails for the RIGHT reason (MISSING_FUNCTIONALITY): the cycle
DOES refuse (so the refuse + exit-code assertions pass), but the reported reason
carries the `des.runtime.freshness.*` notice rather than the gate's real reason,
so the "reported reason names the real cause" / "reported reason is not the
freshness notice" assertions fail with a semantic AssertionError -- never a
collection / import / setup error (pre-DELIVER fail-for-right-reason gate).

A future slice's `.feature` file (slice-02, the NOT_APPLICABLE path) is authored
JIT when that slice enters DELIVER; its scenarios -- when present -- carry an
author-ahead `@skip`/`@pending` tag this hook honours. slice-01 carries no such
tag, so the hook leaves it runnable.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the skip hook is scoped to items collected from
# under here so a session-wide keyword match never poisons unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Author-ahead RED-scaffold marker tags for FUTURE slices. A scenario carrying
# ANY of these is skipped until DELIVER unskips it. slice-01 (the entering slice)
# carries none -- it runs RED now.
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
