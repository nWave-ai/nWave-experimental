"""Shared step bindings reused across slices 01-03 (Mandate-12 SSOT; S1).

The `@when` driving-port action and the two most-common `@then` verdict
assertions (PASS / zero-failing) are declared ONCE here as the single source of
truth and imported by every slice runner via `from ...steps_common import *`.
This is the S1 tolerable-variant "single SSOT module referenced from multiple
slice runners" — one function object, one pytest-bdd registration, no shadow.

Every step body is ≤2 statements and delegates to `composition`
(DevopsWaveMigrationComposition) — zero inline business logic, zero control flow
(Mandate-12 c3). Verdict/exit assertions go through `assert_state_delta` over the
port-exposed universe (Mandate 8).
"""

from __future__ import annotations

from pytest_bdd import then, when

from tests.common.state_delta import assert_state_delta, set_to

from ._universe import GATE_UNIVERSE, snapshot
from .domain_types import Verdict


# --- When (the single driving-port action, SSOT) --------------------------


@when("the maintainer runs the skill-normative gate through the des dispatcher")
def when_run_gate_via_dispatcher(composition, state) -> None:
    state["before"] = snapshot(None)
    composition.run_gate_via_dispatcher()


# --- Then (the two most-common verdict assertions, SSOT) ------------------


@then("the gate verdict is PASS with exit code 0")
def then_verdict_pass(composition, state) -> None:
    after = snapshot(composition.outcome)
    assert_state_delta(
        before=state["before"],
        after=after,
        universe=GATE_UNIVERSE,
        expected={"outcome.exit_code": set_to(composition.expected_exit(Verdict.PASS))},
    )


@then("the verdict reports zero failing instrumentation clauses")
def then_zero_failing_clauses(composition) -> None:
    assert "0 failing" in composition.outcome.stdout
