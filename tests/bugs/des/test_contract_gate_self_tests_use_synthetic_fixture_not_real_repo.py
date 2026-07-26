"""Regression -- two contract-gate self-tests must prove a SCALE-INVARIANT
counting property on a small synthetic fixture, not by paying this repo's
own multi-thousand-item collection/subprocess cost.

DEFECT: two currently-PASSING tests dominate a large slice of this repo's own
suite wall-clock purely to prove a counting property that holds identically
at any suite size:

  - ``tests/des/cli/fix_contract_gate_digest_undercount/steps/
    test_slice_01_canonical_count_parity.py`` (scenario "The print-digest CLI
    fingerprints the full canonical collected scope of the live contract
    suite") -- ``--durations`` measured 130.65s. Its Given step binds
    ``SuiteShape.CANONICAL_LIVE``
    (``tests/des/cli/fix_contract_gate_digest_undercount/steps/
    composition.py:120-126``), which points the real
    ``des run-contract-gate --collect-only --print-digest`` CLI subprocess at
    THIS repo's own live tree.
  - ``tests/des/integration/test_contract_gate_collect_only_count_consistency.py
    ::test_collect_only_node_id_count_matches_run_phase_count`` -- measured
    65.03s. It calls ``_collect_scope(repo)`` directly with
    ``repo = Path(__file__).resolve().parents[3]`` -- again this repo's own
    live tree, in-process.

Charter: ``docs/product/expectations/fix-contract-gate-slow-tests-synthetic-
fixture/two-slow-gate-self-tests-swap-to-synthetic-fixture.md``. The fix
(crafter's job, Phase 3b -- NOT implemented by this AT, test-authoring only,
zero production/target-test edits) swaps both items onto the already-built
but currently-unwired synthetic fixture
(``ContractGateDigestComposition._stage_collapse_prone_project`` /
``SuiteShape.COLLAPSE_PRONE``, ``composition.py:404-439``), completing in low
single-digit seconds while still proving the identical counting property.

This file pins TWO independent contracts:

1. TIMING -- each named item must complete within a generous-but-meaningful
   ceiling (15s -- far above what a ~20-item synthetic fixture needs, far
   below today's 130.65s/65.03s). Measured behaviorally (an actual bounded
   subprocess run, not a source-text proxy) so it cannot be satisfied by a
   cosmetic edit that doesn't actually relocate the cost. RED today: both
   items still pay the real-repo cost, so the bounded subprocess run times
   out well before either item finishes.
2. NON-VACUOUS ORACLE (the important half per the charter) -- the synthetic
   fixture that will receive the swap must not be too trivial to ever fail.
   No dedicated test already proved this (verified below), so it is pinned
   here: the fixture reproduces the EXACT defect this whole feature guards
   against (a naive ``set()``-dedup of ``pytest --collect-only`` stdout,
   which pytest-pspec/pytest-describe collapse to shared docstring/prose
   text -- ``pyproject.toml`` ``pytest-pspec>=0.0.4`` /
   ``pytest-describe>=3.2.0`` -- ADR-001) under a genuinely wrong/undercounted
   digest. Already GREEN today (the fixture already exists, independent of
   whether the two slow tests have been wired to it) -- a capability floor
   that must hold both before and after the swap.

Driving surface: item 1 is driven as its OWN pytest subprocess invocation
(bounded by a timeout), never imported directly -- this file never imports
``des.cli.run_contract_gate`` or the two target tests' production/step
modules. The one production-adjacent import here
(``ContractGateDigestComposition``) is TEST INFRASTRUCTURE (a step-support
module under ``tests/``, not ``src/``), reused verbatim (DRY) rather than
duplicating the fixture-staging logic.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.des.cli.fix_contract_gate_digest_undercount.steps.composition import (
    ContractGateDigestComposition,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]

_SLICE_01_ITEM = (
    "tests/des/cli/fix_contract_gate_digest_undercount/steps/"
    "test_slice_01_canonical_count_parity.py"
    "::test_the_printdigest_cli_fingerprints_the_full_canonical_collected_"
    "scope_of_the_live_contract_suite"
)
_COLLECT_ONLY_ITEM = (
    "tests/des/integration/test_contract_gate_collect_only_count_consistency.py"
    "::TestContractGateCollectOnlyCountConsistency"
    "::test_collect_only_node_id_count_matches_run_phase_count"
)

# Generous vs a ~20-item synthetic fixture, far below today's 130.65s/65.03s
# (per the charter's "e.g. 15 seconds" suggestion).
_TIMING_CEILING_SECONDS = 15.0
_COLLECTED_LINE_RE = re.compile(r"(\d+)\s+tests?\s+collected")


def _completes_within_ceiling(nodeid: str) -> bool:
    """Run one pytest item as its own subprocess, bounded by the ceiling.

    A bounded run (not the full 130s/65.03s) so this regression test itself
    stays cheap even while RED: ``subprocess.run(timeout=...)`` kills the
    child at the ceiling rather than waiting out its real duration.
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", nodeid, "-q", "--tb=no"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_TIMING_CEILING_SECONDS,
        )
        return True
    except subprocess.TimeoutExpired:
        return False


# ===========================================================================
# TIMING PINS -- each item must complete within the ceiling
# ===========================================================================


@pytest.mark.negative_at
def test_canonical_count_parity_scenario_does_not_exceed_timing_ceiling() -> None:
    """The slice-01 walking skeleton must not still pay the live-repo subprocess
    cost (130.65s measured) -- it must complete within the timing ceiling once
    it fingerprints the small synthetic fixture instead."""
    assert _completes_within_ceiling(_SLICE_01_ITEM), (
        f"{_SLICE_01_ITEM} still exceeds the {_TIMING_CEILING_SECONDS}s timing "
        "ceiling (measured 130.65s pre-fix). WHY: its Given step still binds "
        "SuiteShape.CANONICAL_LIVE (tests/des/cli/fix_contract_gate_digest_"
        "undercount/steps/composition.py:120-126), pointing the print-digest "
        "CLI subprocess at this repo's own multi-thousand-item live tree. "
        "HOW: swap the Given step to the already-built synthetic fixture "
        "(SuiteShape.COLLAPSE_PRONE / _stage_collapse_prone_project, "
        "composition.py:404-439) per docs/product/expectations/"
        "fix-contract-gate-slow-tests-synthetic-fixture/"
        "two-slow-gate-self-tests-swap-to-synthetic-fixture.md."
    )


def test_collect_only_count_consistency_does_not_exceed_timing_ceiling() -> None:
    """The collect-only/run-phase parity integration test must not still pay
    the live-repo in-process collection cost (65.03s measured) -- it must
    complete within the timing ceiling once it targets the small synthetic
    fixture instead."""
    assert _completes_within_ceiling(_COLLECT_ONLY_ITEM), (
        f"{_COLLECT_ONLY_ITEM} still exceeds the {_TIMING_CEILING_SECONDS}s "
        "timing ceiling (measured 65.03s pre-fix). WHY: it calls "
        "_collect_scope(repo) with repo = Path(__file__).resolve().parents[3] "
        "-- this repo's own live tree, collected in-process. HOW: point it at "
        "a small synthetic pytest project instead (e.g. reuse "
        "ContractGateDigestComposition._stage_collapse_prone_project, "
        "tests/des/cli/fix_contract_gate_digest_undercount/steps/"
        "composition.py:404-439) per docs/product/expectations/"
        "fix-contract-gate-slow-tests-synthetic-fixture/"
        "two-slow-gate-self-tests-swap-to-synthetic-fixture.md."
    )


# ===========================================================================
# NON-VACUOUS-ORACLE NEGATIVE PIN -- the fixture must not be too trivial to fail
# ===========================================================================


# ===========================================================================
# NEGATIVE SOURCE-SHAPE PIN -- the same policy, a third gate self-test
# ===========================================================================

_SPINE_DOGFOOD_STEPS = (
    _REPO_ROOT
    / "tests/des/acceptance/atdd_pure_spine_dogfood_defects/steps"
    / "test_atdd_pure_spine_dogfood_defects.py"
)


def test_spine_dogfood_digest_given_does_not_target_the_real_repo() -> None:
    """The slice-01 digest scenario must stage its own synthetic clean tree.

    Same policy as the two items above, a third site. Its Given step used to
    return ``composition.repo``, pointing the print-digest CLI at this repo's
    own ~1677-item tree: 40.33s measured on a warm box (92.24s cold), for a
    property that holds at any suite size (a clean populated scope digests to
    a 64-hex non-sentinel value, twice, strict markers preserved). It now
    stages ``CollectScope.REAL_NON_EMPTY``, the fourth member of the same
    closed condition universe its three sibling scenarios already draw from.

    Pinned STATICALLY on purpose. The behavioural timing pin used for the two
    items above is the right tool when the fix is not yet made -- it refuses a
    cosmetic edit that never relocates the cost. Here the swap is done and
    measured, so the pin's only remaining job is to stop the real repo coming
    back; a bounded pytest subprocess would re-pay a slice of the very cost
    this whole file exists to remove. What that choice gives up, stated
    plainly: a re-route to the real repo under some OTHER spelling (a fresh
    ``Path(...).parents[N]``, a new composition attribute) would slip past
    this check. The literal regression -- ``composition.repo`` handed back to
    the gate -- would not.
    """
    source = _SPINE_DOGFOOD_STEPS.read_text(encoding="utf-8")
    marker = '@given("a contract test tree that collects clean"'
    start = source.index(marker)
    end = source.index("\n@", start + 1)
    given_block = source[start:end]

    assert "return composition.repo" not in given_block, (
        "the slice-01 clean-tree Given returns `composition.repo` again -- the "
        "print-digest CLI is back on this repo's own multi-thousand-item tree "
        "(40.33s warm / 92.24s cold, measured). WHY it must not: the property "
        "under test (clean populated scope -> 64-hex non-sentinel digest, "
        "derived idempotently, strict markers preserved) is scale-invariant, "
        "and this repo already ratified the synthetic-fixture trade for its "
        "gate self-tests -- see this file's two timing pins above. HOW to fix: "
        "return `composition.make_test_tree(tmp_path, "
        "CollectScope.REAL_NON_EMPTY)`, which stages the tree and anchors it "
        "mechanically (exit 0, populated under the contract filter) before the "
        "gate ever sees it."
    )


@pytest.mark.negative_at
def test_collapse_prone_fixture_is_not_too_trivial_to_ever_fail(
    tmp_path: Path,
) -> None:
    """The synthetic COLLAPSE_PRONE fixture that will receive the swap must
    still be CAPABLE of exposing a genuine miscount -- otherwise the swap
    would be a false speedup (a smaller fixture too trivial to distinguish a
    correct digest from a broken one), per the charter's explicit negative
    requirement.

    No dedicated test already proves this (confirmed by search -- see this
    file's module docstring); DRY reuse of the existing fixture-staging
    method (``_stage_collapse_prone_project``) rather than a hand-rolled
    duplicate, per the report-back instruction to cite/reuse if found, author
    if not.

    Proof mechanism: feed the fixture through the EXACT historic defect this
    whole feature guards against -- a naive ``set()``-dedup of
    ``pytest --collect-only`` stdout lines. pytest-pspec/pytest-describe
    (real project dependencies, ADR-001) rewrite the parametrized function's
    per-case stdout line to its SHARED docstring, collapsing all 6
    parametrize cases into one identical line; ``set()`` then undercounts
    relative to pytest's own true collected-item count. If this fixture were
    too small/uniform to trigger that collapse, it could never distinguish a
    correct in-process digest from a broken stdout-parsed one.
    """
    composition = ContractGateDigestComposition(tmp_path)
    project = composition._stage_collapse_prone_project()

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        "expected the synthetic fixture to collect cleanly -- got "
        f"returncode={result.returncode}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}"
    )

    match = _COLLECTED_LINE_RE.search(result.stdout)
    assert match, (
        "expected pytest's own '<N> test(s) collected' summary line -- got "
        f"stdout={result.stdout!r}"
    )
    true_collected_count = int(match.group(1))

    stdout_lines = [line for line in result.stdout.splitlines() if "::" in line]
    naive_stdout_dedup_count = len(set(stdout_lines))

    assert naive_stdout_dedup_count < true_collected_count, (
        "the COLLAPSE_PRONE synthetic fixture must reproduce a genuine "
        f"stdout-parse undercount (naive dedup={naive_stdout_dedup_count} "
        f"vs true collected={true_collected_count}) -- it did NOT undercount, "
        "meaning this fixture is too trivial to ever distinguish a correct "
        "digest from a broken one. WHY this matters: swapping the two slow "
        "self-tests onto a fixture that can never fail would be a false "
        "speedup, not a fix (the charter's explicit non-vacuous-oracle "
        "negative requirement). HOW to fix: grow/reshape "
        "_stage_collapse_prone_project (tests/des/cli/"
        "fix_contract_gate_digest_undercount/steps/composition.py:404-439) "
        "until it reproduces the collapse again."
    )
