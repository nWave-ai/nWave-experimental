"""pytest-bdd binding for f-nonbypassable-attestation slice-06 (skip authorization).

The SKIP-AUTHORIZATION half of the split slice-05 (carpaccio sizing fix
2026-06-16: the original slice-05 carried 10 scenarios, over the carpaccio
ceiling of 5). slice-05 (guard half) = the 5 guard-verdict states. slice-06 (skip half) = these 5 skip-authorization
states (form-valid-witness->allow / empty-rationale-witness->block / valid-pre-
grant->allow / expired-pre-grant->block / malformed-input->exit 2).

RUNTIME ALREADY BUILT BY slice-05 (guard half): slice-06 (skip half)'s DELIVER is ATs-only -- the production guard
(``wave_dispatch_guard_policy`` + the ``verify_wave_dispatch`` gate + ``dispatch.pre``
+ installer) is shipped by slice-05 (guard half). slice-06 (skip half) drives the SAME in-tree gate to exercise the
skip-authorization branches (witness FORM check + session pre-grant freshness read)
+ the malformed-input verdict. Step bodies delegate to the shared composition root
(composition_slice_05.py); no business logic in step bodies (Mandate-12). HERMETIC:
drives the gate via ``python -m des.cli.verify_wave_dispatch`` ARGS + a tmp fixture
prompt FILE -- no developer home-directory read anywhere.

Driving surface (Mandate-13, Layer-3 subprocess): ``python -m
des.cli.verify_wave_dispatch`` with ``--subagent-type``/``--prompt-path``/
``--repo-root``/``--session-id``. observable = exit code (ALLOW=0 / BLOCK=1 /
malformed=2) + the one JSON line on stdout.

S1 (step-text uniqueness): the wave-dispatch guard verbs shared with slice-05 (guard half) ("the
orchestrator dispatches a wave-owner agent", "the dispatch carries no DES-WAVE
marker", "the orchestrator dispatches the agent", "the dispatch is allowed and
names the recognized on-spine signal", "the dispatch is blocked with a warn-and-ask
reason") are registered per-MODULE: this module's scope (the slice-06 (skip half) feature) is
disjoint from the slice-05 (guard half) module's scope -- no last-loaded shadow across modules. The
skip-authorization Given verbs ("a wave-skip witness with a non-empty rationale is
recorded", etc.) and the malformed verbs are UNIQUE to slice-06 (skip half). The done-gate verbs in
conftest are a different vocabulary; no key collision.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-05 (guard half)'s DELIVER ships the
``wave_dispatch_guard_policy`` (incl. the generalized wave-parametric skip-witness
FORM check + the session pre-grant freshness read) + the ``verify_wave_dispatch``
gate + the ``dispatch.pre`` composition row (DDD-9). At HEAD the gate module is
absent, so the subprocess exits non-zero (NEITHER ALLOW=0 nor BLOCK=1) -> semantic
AssertionErrors against the expected verdict.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, scenarios, then, when

from .composition_slice_05 import WaveDispatchGuardComposition, guard  # noqa: F401
from .domain_types_nonbypassable import WaveOwner


scenarios("../slice-06-wave-skip-authorization.feature")


# --- Given (slice-06) -----------------------------------------------------


@given("the orchestrator dispatches a wave-owner agent")
def given_wave_owner(guard: WaveDispatchGuardComposition, tmp_path: Path) -> None:
    guard.use_project_root(tmp_path)
    guard.given_wave_owner(WaveOwner.SOLUTION_ARCHITECT)


@given("the dispatch carries no DES-WAVE marker")
def given_no_marker(guard: WaveDispatchGuardComposition) -> None:
    guard.given_no_des_wave_marker()


@given("a wave-skip witness with a non-empty rationale is recorded")
def given_form_valid_witness(guard: WaveDispatchGuardComposition) -> None:
    guard.write_wave_skip_witness(
        "DESIGN", "Trivial config-only change; reuse-first holds."
    )


@given("a wave-skip witness with an empty rationale is recorded")
def given_form_invalid_witness(guard: WaveDispatchGuardComposition) -> None:
    guard.write_wave_skip_witness("DESIGN", "")


@given("a non-expired session pre-grant is recorded")
def given_valid_pre_grant(guard: WaveDispatchGuardComposition) -> None:
    guard.write_session_pre_grant(ttl_seconds=3600)


@given("an expired session pre-grant is recorded")
def given_expired_pre_grant(guard: WaveDispatchGuardComposition) -> None:
    guard.write_session_pre_grant(ttl_seconds=-1)


# --- When (slice-06) ------------------------------------------------------


@when("the orchestrator dispatches the agent")
def when_dispatch(guard: WaveDispatchGuardComposition) -> None:
    guard.when_agent_dispatched()


@when("the orchestrator dispatches the agent without naming the subagent type")
def when_dispatch_malformed(guard: WaveDispatchGuardComposition) -> None:
    guard.when_dispatched_without_subagent_type()


# --- Then (slice-06) ------------------------------------------------------


@then("the dispatch is allowed and names the recognized on-spine signal")
def then_allowed_recognized(guard: WaveDispatchGuardComposition) -> None:
    guard.then_wave_owner_allowed_on_spine()


@then("the dispatch is blocked with a warn-and-ask reason")
def then_blocked(guard: WaveDispatchGuardComposition) -> None:
    guard.then_block_warns_and_asks()


@then("the dispatch is rejected as malformed input")
def then_malformed(guard: WaveDispatchGuardComposition) -> None:
    guard.then_malformed_input_is_rejected()
