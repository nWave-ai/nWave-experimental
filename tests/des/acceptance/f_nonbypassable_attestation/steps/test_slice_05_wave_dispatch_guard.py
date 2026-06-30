"""pytest-bdd binding for f-nonbypassable-attestation slice-05 (guard verdicts).

The GUARD-VERDICT half of the split slice-05 (carpaccio sizing fix 2026-06-16:
the original slice-05 carried 10 scenarios, over the carpaccio ceiling of 5).
slice-05 (guard half) = the 5 guard-verdict states (BLOCK-no-marker + the four ALLOW recognitions:
matching-marker / platform-architect design / platform-architect devops /
reviewer-exempt). slice-06 (skip half) = the 5 skip-authorization states.

The SUT is the IN-TREE gate ``des.cli.verify_wave_dispatch`` (a runtime `des.cli`
gate mirroring ``verify_readiness_pre_dispatch.py``), composed onto ``dispatch.pre``
-- NOT the hand-placed ``~/.claude`` personal hook (which has no repo source --
DDD-8). Step bodies delegate to the shared composition root (composition_slice_05.py);
no business logic in step bodies (Mandate-12). HERMETIC: drives the gate via
``python -m des.cli.verify_wave_dispatch`` ARGS + a tmp fixture prompt FILE -- no
developer home-directory read anywhere (the acceptance-hermeticity guard forbids it).

Driving surface (Mandate-13, Layer-3 subprocess): ``python -m
des.cli.verify_wave_dispatch`` with ``--subagent-type``/``--prompt-path``/
``--repo-root``/``--session-id``. observable = exit code (ALLOW=0 / BLOCK=1) +
the one JSON line on stdout.

S1 (step-text uniqueness): the slice-05 guard verbs ("the orchestrator dispatches
the agent", "the dispatch is allowed and names the recognized on-spine signal",
"the dispatch is blocked with a warn-and-ask reason") are UNIQUE to the wave-
dispatch guard. They appear in BOTH slice-05 (guard half) and slice-06 (skip half), but pytest-bdd registers step
decorators per-MODULE: this module's scope (the slice-05 (guard half) feature) and the slice-06 (skip half) module's
scope are disjoint -- no last-loaded shadow across modules. The done-gate verbs in
conftest are a different vocabulary (the done-gate, not the guard); no key collision.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-05 (guard half)'s DELIVER ships the
``wave_dispatch_guard_policy`` (wave->owner map + ``DISPATCH_GUARD_VOCABULARY``) +
the ``verify_wave_dispatch`` gate + the ``dispatch.pre`` composition row (DDD-8).
At HEAD the gate module is absent, so the subprocess exits non-zero (NEITHER
ALLOW=0 nor BLOCK=1) -> semantic AssertionErrors against the expected verdict.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, scenarios, then, when

from .composition_slice_05 import WaveDispatchGuardComposition, guard  # noqa: F401
from .domain_types_nonbypassable import WaveOwner


scenarios("../slice-05-wave-dispatch-guard.feature")


# --- Given (slice-05) -----------------------------------------------------


@given("the orchestrator dispatches a wave-owner agent")
def given_wave_owner(guard: WaveDispatchGuardComposition, tmp_path: Path) -> None:
    guard.use_project_root(tmp_path)
    guard.given_wave_owner(WaveOwner.SOLUTION_ARCHITECT)


@given("the orchestrator dispatches the platform architect agent")
def given_platform_architect(
    guard: WaveDispatchGuardComposition, tmp_path: Path
) -> None:
    guard.use_project_root(tmp_path)
    guard.given_platform_architect()


@given("the orchestrator dispatches a reviewer agent")
def given_reviewer(guard: WaveDispatchGuardComposition, tmp_path: Path) -> None:
    guard.use_project_root(tmp_path)
    guard.given_reviewer()


@given("the dispatch carries no DES-WAVE marker")
def given_no_marker(guard: WaveDispatchGuardComposition) -> None:
    guard.given_no_des_wave_marker()


@given("the dispatch carries the matching DES-WAVE marker")
def given_matching_marker(guard: WaveDispatchGuardComposition) -> None:
    guard.given_matching_des_wave_marker()


@given("the dispatch carries the design wave marker")
def given_design_marker(guard: WaveDispatchGuardComposition) -> None:
    guard.given_wave_marker("design")


@given("the dispatch carries the devops wave marker")
def given_devops_marker(guard: WaveDispatchGuardComposition) -> None:
    guard.given_wave_marker("devops")


# --- When (slice-05) ------------------------------------------------------


@when("the orchestrator dispatches the agent")
def when_dispatch(guard: WaveDispatchGuardComposition) -> None:
    guard.when_agent_dispatched()


# --- Then (slice-05) ------------------------------------------------------


@then("the dispatch is allowed and names the recognized on-spine signal")
def then_allowed_recognized(guard: WaveDispatchGuardComposition) -> None:
    guard.then_wave_owner_allowed_on_spine()


@then("the reviewer dispatch is always allowed")
def then_reviewer_allowed(guard: WaveDispatchGuardComposition) -> None:
    guard.then_reviewer_always_allowed()


@then("the dispatch is blocked with a warn-and-ask reason")
def then_blocked(guard: WaveDispatchGuardComposition) -> None:
    guard.then_block_warns_and_asks()
