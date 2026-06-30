"""Step bindings: an unrecognised whole-tree target falls back to pytest (slice-04 / D9).

Layer-3 subprocess e2e (Mandate-13). Each step body delegates to the SAME
``WholeTreeGateComposition`` the slice-01 keystone established (REUSE: the
combined-channel ``GateOutcome`` event parse + the subprocess driving port),
EXTENDED only with a lockfile-less fixture + a both-legs driver. No inline
business logic (Mandate-12 criterion 3); domain nouns are typed via
``domain_types`` (criterion 1); the composition service signatures consume those
typed parameters (criterion 2). The given/when delegates are RE-DECLARED here
(module-local to this ``scenarios()`` binding) so there is no cross-slice
pytest-bdd collision -- the logic SSOT stays in the composition.

REUSED slice-01/02/03 DSL (Mandate-12 step reuse):
  * ``WholeTreeGateComposition`` -- the subprocess driving port (composition.py)
  * ``given_polyglot_root`` / ``run_whole_tree_digest_mode`` -- scenario-2 reuses
    the slice-03 polyglot staging + the slice-02 digest-mode driver verbatim
  * ``GateOutcome.resolution_event`` / ``indeterminate_event`` /
    ``indeterminate_reason`` -- the slice-01/03 observable accessors
  * ``DigestMode`` / ``POLYGLOT_LOCKFILES`` / ``PYTEST_RUNNER`` /
    ``WHOLE_TREE_INDETERMINATE_EXIT`` -- the slice-02/03 typed domain vocabulary
NET-NEW (slice-04): ``given_unrecognized_target`` + ``TargetKind.UNRECOGNIZED``
  + ``run_whole_tree_run_and_digest_legs`` + ``GateOutcome.fell_back_to_pytest`` /
  ``degraded_loud_indeterminate``.

active-RED (atdd_pure): at HEAD ``resolve(repo, None)`` returns the 0-lockfile
``Indeterminate`` (no ``UnrecognizedRunner`` subtype yet), and BOTH whole-tree
routers degrade EVERY ``Indeterminate`` to exit-3 -- so a lockfile-less target
gets no pytest fallback. Scenario 1 RED-fails for the right reason (missing
functionality: the D9 discriminant + the two router pre-checks). Scenario 2 is a
GREEN-by-construction over-correction guard (the polyglot degrade is already
correct at HEAD and must STAY correct after the fix; it RED-fails only if DELIVER
over-corrects the ``Indeterminate`` branch). DELIVER ships the discriminant to
turn scenario 1 GREEN while keeping scenario 2 GREEN. The composition imports ONLY
stdlib + subprocess, so the suite COLLECTS cleanly (RED, not BROKEN).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import WholeTreeGateComposition
from .domain_types import (
    POLYGLOT_LOCKFILES,
    PYTEST_RUNNER,
    DigestMode,
)


scenarios("../slice-04-unrecognized-pytest-fallback.feature")


@pytest.fixture
def composition() -> WholeTreeGateComposition:
    """Production-wired driving port over the real run-contract-gate CLI."""
    return WholeTreeGateComposition()


# --- Given -------------------------------------------------------------------


@given("a repository with no recognised test-runner lockfile")
def given_unrecognized(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_unrecognized_target(tmp_path)


@given("a polyglot repository root with no whole-tree runner declaration")
def given_polyglot_no_declaration(
    composition: WholeTreeGateComposition, tmp_path: Path
) -> None:
    composition.given_polyglot_root(tmp_path)


# --- When --------------------------------------------------------------------


@when(
    "the maintainer runs the whole-tree contract gate on both the run leg and the digest leg"
)
def when_run_both_legs(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_run_and_digest_legs()


@when("the maintainer runs the whole-tree digest leg against the root")
def when_run_digest_leg(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_digest_mode(DigestMode.COMMITTED_SCOPE_DIGEST)


# --- Then: scenario 1 -- the active-RED witness (BOTH routers fall back) ------


@then(
    "both legs fall back to the pytest runner and neither degrades to an "
    "ambiguous-runner refusal"
)
def then_both_legs_fall_back(composition: WholeTreeGateComposition) -> None:
    run = composition.run_leg()
    digest = composition.digest_leg()
    assert (
        run.fell_back_to_pytest()
        and not run.degraded_loud_indeterminate()
        and digest.fell_back_to_pytest()
        and not digest.degraded_loud_indeterminate()
    ), (
        "an UNRECOGNISED (0-lockfile) `--repo` target must FALL BACK to pytest on "
        f"BOTH whole-tree routers -- each leg emitting WholeTreeRunnerResolved"
        f"(runner={PYTEST_RUNNER!r}, routed=False) and NEVER the "
        "health.gate.whole-tree-runner.indeterminate refusal / exit-3 (ADR-FLOW-011 "
        "D9). The run leg (_maybe_route_through_runner_whole_tree) and the digest leg "
        "(_maybe_route_digest_through_runner) share the IDENTICAL conflation, so BOTH "
        "must be pinned -- fixing only the digest leg leaves the run leg regressed. "
        "At HEAD both routers degrade EVERY Indeterminate (including the 0-lockfile "
        "case) to exit-3, so no pytest fallback resolution event is emitted. "
        f"{composition.diag_both_legs()}"
    )


# --- Then: scenario 2 -- the over-correction guard (polyglot still degrades) --


@then(
    "the gate still refuses indeterminate and names the competing lockfiles, "
    "never falling back to pytest"
)
def then_polyglot_still_degrades(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    reason = obs.indeterminate_reason()
    assert (
        obs.degraded_loud_indeterminate()
        and all(lockfile in reason for lockfile in POLYGLOT_LOCKFILES)
        and obs.resolution_event() is None
    ), (
        "a POLYGLOT root with NO `.nwave/runner.json` is genuinely AMBIGUOUS and must "
        "STILL degrade LOUD INDETERMINATE naming BOTH competing lockfiles "
        f"({POLYGLOT_LOCKFILES!r}) -- the D9 unrecognised->pytest fallback must change "
        "ONLY the 0-lockfile UnrecognizedRunner branch and must NOT over-correct the "
        "bare-Indeterminate polyglot path into a pytest fallback (that would re-break "
        "the D8 polyglot escape hatch). The over-correction guard: a "
        "WholeTreeRunnerResolved event on a declaration-less polyglot root is the "
        "over-correction symptom (the fix swallowed a genuine ambiguity). "
        f"{composition.diag()}"
    )
