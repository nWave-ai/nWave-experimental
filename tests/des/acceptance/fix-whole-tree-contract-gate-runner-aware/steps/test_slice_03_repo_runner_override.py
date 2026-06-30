"""Step bindings: a polyglot root declares its whole-tree runner (slice-03 / D8).

Layer-3 subprocess e2e (Mandate-13). Each step body delegates to the SAME
``WholeTreeGateComposition`` the slice-01 keystone established (REUSE: the
combined-channel ``GateOutcome`` event parse + the subprocess driving port),
EXTENDED only with polyglot-root staging + a ``.nwave/runner.json`` writer. No
inline business logic (Mandate-12 criterion 3); domain nouns are typed via
``domain_types`` (criterion 1); the composition service signatures consume those
typed parameters (criterion 2). The given/when delegates are RE-DECLARED here
(module-local to this ``scenarios()`` binding) so there is no cross-slice
pytest-bdd collision -- the logic SSOT stays in the composition.

active-RED (atdd_pure): at HEAD ``resolve(repo, None)`` never consults
``.nwave/runner.json`` (``_repo_runner_override`` + ``read_repo_runner_json`` are
absent), so a declared polyglot root still degrades to the polyglot
``Indeterminate`` naming the competing lockfiles. Scenarios 1-3 RED-fail for the
right reason (missing functionality: the D8 override seam); scenarios 4-5 are
GREEN-by-construction no-regression witnesses (the D2 polyglot refusal + the
single-lockfile fast-path are byte-unchanged by the override). DELIVER ships the
override seam to turn 1-3 GREEN. The composition imports ONLY stdlib + subprocess,
so the suite COLLECTS cleanly (RED, not BROKEN).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import WholeTreeGateComposition
from .domain_types import (
    CARGO_RUNNER,
    POLYGLOT_LOCKFILES,
    PYTEST_RUNNER,
    REPO_RUNNER_OVERRIDE_FILE,
    UNREGISTERED_RUNNER_NAME,
    WHOLE_TREE_INDETERMINATE_EXIT,
    RepoRunnerOverride,
    TargetKind,
)


scenarios("../slice-03-repo-runner-override.feature")


@pytest.fixture
def composition() -> WholeTreeGateComposition:
    """Production-wired driving port over the real run-contract-gate CLI."""
    return WholeTreeGateComposition()


# --- Given -------------------------------------------------------------------


@given("a polyglot repository root the contract gate cannot disambiguate on its own")
def given_polyglot_root(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_polyglot_root(tmp_path)


@given("a single-lockfile Python target the contract gate can run against")
def given_python_target(composition: WholeTreeGateComposition, tmp_path: Path) -> None:
    composition.given_single_lockfile_target(TargetKind.PYTHON, tmp_path)


@given("the maintainer declares the whole-tree runner as cargo in the repository")
def given_declares_cargo(composition: WholeTreeGateComposition) -> None:
    composition.declare_repo_runner(RepoRunnerOverride.VALID_CARGO)


@given("the maintainer declares an unregistered whole-tree runner in the repository")
def given_declares_unknown(composition: WholeTreeGateComposition) -> None:
    composition.declare_repo_runner(RepoRunnerOverride.UNKNOWN_KEY)


@given(
    "the maintainer leaves a malformed whole-tree runner declaration in the repository"
)
def given_declares_malformed(composition: WholeTreeGateComposition) -> None:
    composition.declare_repo_runner(RepoRunnerOverride.MALFORMED_JSON)


# --- When --------------------------------------------------------------------


@when("the maintainer runs the whole-tree contract gate against the root")
def when_run_against_root(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_gate()


@when("the maintainer runs the whole-tree contract gate against the target")
def when_run_against_target(composition: WholeTreeGateComposition) -> None:
    composition.run_whole_tree_gate()


# --- Then: scenario 1 -- the keystone (declared cargo honoured) --------------


@then(
    "the gate honours the declared cargo runner and routes the whole-tree run through it"
)
def then_honours_declared_cargo(composition: WholeTreeGateComposition) -> None:
    ev = composition.observable().resolution_event()
    assert (
        ev is not None and ev.get("runner") == CARGO_RUNNER and ev.get("routed") is True
    ), (
        'on a polyglot root with `.nwave/runner.json {"runner": "cargo-test"}` the '
        "whole-tree gate must CONSULT the repo-level declaration (feature is None), "
        f"resolve cargo ({CARGO_RUNNER!r}) BYPASSING the lockfile-scan, and emit a "
        "WholeTreeRunnerResolved preamble event (routed=True) -- present regardless of "
        "cargo availability -- but at HEAD `resolve(repo, None)` never reads "
        ".nwave/runner.json, so the polyglot root degrades to INDETERMINATE and no "
        f"resolution event is emitted. {composition.diag()}"
    )


@then("the gate never refuses the declared polyglot root as an ambiguous lockfile set")
def then_no_polyglot_refusal(composition: WholeTreeGateComposition) -> None:
    assert not composition.observable().announced_polyglot_ambiguity(), (
        "a honoured `.nwave/runner.json` declaration RESOLVES the runner BEFORE the "
        "lockfile-scan, so the LOUD 'polyglot target' ambiguity refusal must NOT fire "
        "on a declared root -- but at HEAD the override is never consulted and the "
        "polyglot scan refuses, naming the competing lockfiles. (cargo-availability-"
        "robust: a cargo-absent RUN-leg degrade names the cargo runner, NOT 'polyglot "
        f"target'.) {composition.diag()}"
    )


# --- Then: scenario 2 -- unknown declared runner refused, never guessed ------


@then("the gate refuses indeterminate and names the unregistered runner declaration")
def then_refuses_unknown_named(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    reason = obs.indeterminate_reason()
    assert (
        obs.indeterminate_event() is not None
        and UNREGISTERED_RUNNER_NAME in reason
        and REPO_RUNNER_OVERRIDE_FILE in reason
    ), (
        "a declared but UNREGISTERED whole-tree runner must degrade LOUD INDETERMINATE "
        f"whose reason names the unregistered key ({UNREGISTERED_RUNNER_NAME!r}) AND the "
        f"{REPO_RUNNER_OVERRIDE_FILE!r} declaration it came from -- never guessed -- but "
        "at HEAD the override is never read, so the reason names only the competing "
        f"lockfiles + the feature-scoped docs/feature/<id>/runner.json. {composition.diag()}"
    )


@then("the gate never resolves a runner for the unrecognised declaration")
def then_no_resolution_for_unknown(composition: WholeTreeGateComposition) -> None:
    assert composition.observable().resolution_event() is None, (
        "an unregistered declared runner must NEVER yield a WholeTreeRunnerResolved "
        "event -- the gate refuses INDETERMINATE rather than guess a runner for the "
        f"unrecognised key. {composition.diag()}"
    )


# --- Then: scenario 3 -- malformed declaration degrades loud, no crash -------


@then("the gate refuses indeterminate and names the malformed runner declaration")
def then_refuses_malformed_named(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    assert (
        obs.indeterminate_event() is not None
        and REPO_RUNNER_OVERRIDE_FILE in obs.indeterminate_reason()
    ), (
        f"a malformed {REPO_RUNNER_OVERRIDE_FILE!r} (bad JSON) must degrade LOUD "
        "INDETERMINATE whose reason names the malformed declaration (the override "
        "helper catches json.JSONDecodeError) -- but at HEAD the override is never "
        "read, so the reason names only the competing lockfiles + the feature-scoped "
        f"docs/feature/<id>/runner.json (no `.nwave/` prefix). {composition.diag()}"
    )


@then("the gate never crashes on the malformed declaration")
def then_no_crash_on_malformed(composition: WholeTreeGateComposition) -> None:
    obs = composition.observable()
    assert (
        not obs.emitted_python_traceback()
        and obs.exit_code == WHOLE_TREE_INDETERMINATE_EXIT
    ), (
        "a malformed runner declaration must be CAUGHT and turned into a clean "
        f"INDETERMINATE refusal (exit {WHOLE_TREE_INDETERMINATE_EXIT}), NEVER an "
        "uncaught Python traceback / non-deterministic crash -- the JSONDecodeError "
        f"is caught at the resolution seam, never propagated. {composition.diag()}"
    )


# --- Then: scenario 4 -- polyglot, no declaration (D2 no-regression) ---------


@then("the gate refuses indeterminate and names the competing lockfiles")
def then_refuses_naming_lockfiles(composition: WholeTreeGateComposition) -> None:
    reason = composition.observable().indeterminate_reason()
    assert composition.observable().indeterminate_event() is not None and all(
        lockfile in reason for lockfile in POLYGLOT_LOCKFILES
    ), (
        "a polyglot root with NO `.nwave/runner.json` must preserve today's D2 "
        "behaviour: degrade LOUD INDETERMINATE naming BOTH competing lockfiles "
        f"({POLYGLOT_LOCKFILES!r}) -- the no-regression witness that the D8 override "
        f"pre-check did not weaken the polyglot refusal. {composition.diag()}"
    )


@then("the gate never silently picks one of the competing runners")
def then_no_silent_pick(composition: WholeTreeGateComposition) -> None:
    assert composition.observable().resolution_event() is None, (
        "with no declaration to disambiguate a polyglot root, the gate must NEVER "
        "emit a WholeTreeRunnerResolved event -- it refuses rather than silently pick "
        f"the first lockfile (Invariant 2 / no-silent-pass). {composition.diag()}"
    )


# --- Then: scenario 5 -- single lockfile, no declaration (zero-config) -------


@then("the gate resolves the target's runner to pytest with no declaration needed")
def then_single_lockfile_zero_config(composition: WholeTreeGateComposition) -> None:
    ev = composition.observable().resolution_event()
    assert (
        ev is not None
        and ev.get("runner") == PYTEST_RUNNER
        and ev.get("routed") is False
    ), (
        "a single-pyproject.toml root with NO `.nwave/runner.json` must resolve pytest "
        f"({PYTEST_RUNNER!r}, router -> None, routed=False) via the single-lockfile "
        "fast-path -- the no-regression witness that the D8 `feature is None` override "
        "pre-check leaves the zero-config common case byte-unchanged. "
        f"{composition.diag()}"
    )
