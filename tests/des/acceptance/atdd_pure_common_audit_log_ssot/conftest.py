"""pytest-bdd configuration for the fix-atdd-pure-common-audit-log-ssot suite.

DISTILL-authored RED scaffold (ADR-025): the slice's `.feature` is authored
ahead of the production refactor. The production
``AtCompletionLedger(project_root)`` singleton-shape API does NOT YET exist
(current API is feature-scoped), the ``.nwave/audit/atdd-pure-events.jsonl``
substrate does NOT YET exist, the ``correlation_id`` field is NOT YET
written, the ``LedgerIntegrityViolation`` diagnostic does NOT YET name the
line number or link the repair doc, AND the arch test file does NOT YET
exist in ``tests/build/``. Every scenario reds for the RIGHT reason --
MISSING_FUNCTIONALITY (production behaviour absent), not ImportError /
FixtureBroken / SetupFailure (Pre-DELIVER fail-for-right-reason gate).

The collection hook below marks every slice-01 scenario `xfail(strict=False)`
until DELIVER greens it slice-by-slice.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here so a session-wide `@slice-NN` keyword match never poisons
# unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Every slice is author-ahead RED until DELIVER greens it. DELIVER removes a
# tag from this set as its slice greens. slice-01 has shipped (commit
# d5926cc57); slice-02 is the author-ahead RED scaffold for the 11-caller
# migration cascade; slice-02b is the cascade-regression mitigation that adds
# the `feature_id=` kw-only filter to the three aggregate readers consumed by
# `verify_deliver_integrity._verify_atdd_pure`. Both slice-02 and slice-02b
# RED today: slice-02b reds with TypeError on the unknown kwarg pre-DELIVER;
# AT-3 (the verify-integrity CLI regression-pin) reds with a false-PASS on
# the wrong feature pre-DELIVER. xfail strict=False tolerates the organic
# pass when the slice-02b crafter ships the reader API.
#
# slice-02d-N0 GREENED 2026-05-25 (M45 substrate + M47 AT amendment): the
# helper dual-shape contract is live and both AT-N0a (regression-pin,
# legacy-shape) and AT-N0b (forward-pin, singleton-shape) pass organically.
#
# slice-02c-A DISTILL author-ahead RED (M58, 2026-05-25): the gate-event
# affinity bundle ATs (AT-A1 parametrize-Outline 6 callsites + AT-A2 multi-
# feature filter forward-pin + AT-A3 cross-feature isolation PBT) ship as
# RED scaffold under this conftest. xfail strict=False tolerates the
# organic pass once the slice-02c-A A_GREEN_ATS crafter ships the 6-
# production-callsite + 16-fixture-fanout atomic bundle (per M51 H3
# SUBSTRATE-AFFINITY decomposition).
# Empty under F-CONSOLIDATION-FUTURE-SLICE-CANON (ratified A, future-absent):
# slice-02/02b/02c-A migration scaffolds removed off disk (deferred to backlog,
# re-authored JIT via nw-refactor). Only the delivered slice-01 core remains —
# no author-ahead RED scaffold to xfail. Hook is now a no-op for xfail (xdist
# group pinning below still applies).
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN.

    `strict=False` so a scenario that organically passes (e.g. the
    arch-test PASS row for an all-clean caller tree) does not XPASS-fail
    the suite. The genuine RED rows (singleton-shape API missing, common
    log path absent, correlation_id absent, CLI diagnostic incomplete,
    arch test file absent) fail organically today and will be lifted by
    DELIVER's slice-01 refactor.
    """
    # StepDefinitionNotFoundError tolerates author-ahead scaffolds where
    # DISTILL ships .feature + composition stubs but the @when(...) bindings
    # are deferred to the next phase (slice-02d-N0 empirical: M43 BG ran out
    # of context mid-edit, foreground binding completion 2026-05-25).
    from pytest_bdd.exceptions import StepDefinitionNotFoundError

    xfail = pytest.mark.xfail(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation",
        strict=False,
        raises=(
            AssertionError,
            ModuleNotFoundError,
            ImportError,
            TypeError,
            StepDefinitionNotFoundError,
        ),
    )
    # Parallel-load pinning: this suite scans the real repo tree / spawns
    # cwd=<real repo> subprocesses over the AtCompletionLedger substrate.
    # Pin every item to one xdist worker group so the contract gate's
    # `-n auto --dist loadgroup` cannot race them across workers (NOT
    # masking -- they run honestly, serialized within one worker).
    scan_group = pytest.mark.xdist_group("real_repo_scan")
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        item.add_marker(scan_group)
        if set(item.keywords) & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
