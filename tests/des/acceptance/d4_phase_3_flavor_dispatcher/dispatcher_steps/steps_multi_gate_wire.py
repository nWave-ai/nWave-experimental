"""Step bindings for D4 Phase 3 slice-05 multi-gate dispatch.pre wire.

Mandate-12 criterion 3 -- every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/`while`/
`try`) in step bodies. The DSL emerges from typed enum resolution at the
composition boundary (`GateIdOnDispatchPre`, `BlockEventName`) plus the
existing `InterceptVerdict` enum.

Mandate-13 (S2 driving-port-only) -- step modules import ONLY the slice-05
composition root from conftest + `domain_types` enums. ZERO
`from des.<domain|application|adapters>.<x> import <internal>`
direct-domain imports. The public driving-port entries are
`MultiGateWireComposition.evaluate()` (the multi-gate call shape with
both runners) and `MultiGateWireComposition.evaluate_slice_02_call_shape()`
(the slice-02 backward-compat call shape with only carpaccio_runner).
Both invoke `evaluate_atdd_pure_dispatch(...)` -- the same public surface
slice-02 exposes; the slice-05 crafter extends the signature with an
ADDITIVE `readiness_runner` parameter (default None preserves slice-02
callers).

S1 step-text uniqueness -- every literal `@given/@when/@then` arg in this
module is unique within the `d4_phase_3_flavor_dispatcher` feature scope
(distinct from `steps_dispatcher.py` slice-01, `steps_carpaccio_refactor.py`
slice-02, `steps_readiness_gate.py` slice-03, `steps_log_persistence.py`
slice-04 literals). The slice-05 module talks about "the multi-gate
dispatch composition" / "the atdd_pure flavor wires..." / "the readiness
gate runner is programmed..." -- no collision across the five sibling step
modules in the feature directory.
"""

from __future__ import annotations

from pytest_bdd import given, then, when

from .domain_types import BlockEventName, GateIdOnDispatchPre, InterceptVerdict


# --- Background ------------------------------------------------------------


@given("a tmp_path flavors directory monkey-patched onto the intercept")
def given_flavors_dir_bound(multi_gate_composition) -> None:
    multi_gate_composition.bind_flavors_dir_monkeypatch()


# --- Given: flavor YAML authoring ------------------------------------------


@given(
    "the atdd_pure flavor wires verify-readiness-pre-dispatch ahead of "
    "carpaccio-slice-gate on dispatch.pre"
)
def given_multi_gate_flavor_wire(multi_gate_composition) -> None:
    multi_gate_composition.author_multi_gate_atdd_pure_flavor()


# --- Given: per-gate runner programming -----------------------------------


@given("the readiness gate runner is programmed to clear the dispatch")
def given_readiness_clears(multi_gate_composition) -> None:
    multi_gate_composition.program_readiness_runner_to_clear()


@given("the readiness gate runner is programmed to block the dispatch")
def given_readiness_blocks(multi_gate_composition) -> None:
    multi_gate_composition.program_readiness_runner_to_block()


@given("the carpaccio gate runner is programmed to clear the entering slice")
def given_carpaccio_clears(multi_gate_composition) -> None:
    multi_gate_composition.program_carpaccio_runner_to_clear()


@given("the carpaccio gate runner is programmed to block the entering slice")
def given_carpaccio_blocks(multi_gate_composition) -> None:
    multi_gate_composition.program_carpaccio_runner_to_block()


# --- Given: dispatch prompt authoring -------------------------------------


@given("a dispatch prompt carrying valid atdd_pure markers for a fresh slice")
def given_fresh_slice_prompt(multi_gate_composition) -> None:
    multi_gate_composition.author_fresh_slice_prompt()


# --- When: evaluate -------------------------------------------------------


@when("the multi-gate intercept evaluates the dispatch")
def when_multi_gate_evaluates(multi_gate_composition) -> None:
    multi_gate_composition.evaluate()


@when(
    "the multi-gate intercept evaluates the dispatch in the slice-02 "
    "single-gate call shape"
)
def when_evaluates_slice_02_call_shape(multi_gate_composition) -> None:
    multi_gate_composition.author_slice_02_single_gate_flavor()
    multi_gate_composition.evaluate_slice_02_call_shape()


# --- Then: observable InterceptDecision shape + invocation log -----------
#
# The Then assertions read enum-typed observables off the composition (the
# composition's accessors translate the raw `InterceptDecision.event: str`
# into a typed `BlockEventName` enum + the raw exit_code +
# `InterceptDecision.is_block/is_atdd_pure` into the `InterceptVerdict`
# enum). Step bodies stay <=2 statements per Mandate-12 criterion 3.


@then("the dispatch verdict is a multi-gate allow decision")
def then_verdict_is_multi_gate_allow(multi_gate_composition) -> None:
    assert multi_gate_composition.last_verdict() is InterceptVerdict.ALLOW


@then("the block event names the readiness rejection")
def then_block_event_is_readiness(multi_gate_composition) -> None:
    assert (
        multi_gate_composition.last_block_event()
        is BlockEventName.READINESS_GATE_REJECTED
    )


@then("the block event names the carpaccio rejection")
def then_block_event_is_carpaccio(multi_gate_composition) -> None:
    assert (
        multi_gate_composition.last_block_event()
        is BlockEventName.CARPACCIO_GATE_REJECTED
    )


# --- Then: invocation-log observable ordering ----------------------------
#
# Four explicit @then decorators for the four observable invocation
# orderings -- "verify-readiness then carpaccio" (both invoked, succession
# order, AT-1), "verify-readiness only" (halt-before-carpaccio, AT-2),
# "verify-readiness followed by carpaccio" (both invoked even though
# carpaccio rejected, AT-3 -- the readiness gate is the only halting gate
# per `on_failure: block` ordering), and "carpaccio only" (slice-02
# single-gate call shape, AT-4 backward-compat).


@then(
    "the invocation log records verify-readiness-pre-dispatch then carpaccio-slice-gate"
)
def then_invocation_log_records_both_in_order(multi_gate_composition) -> None:
    assert multi_gate_composition.last_invocation_log() == [
        GateIdOnDispatchPre.VERIFY_READINESS_PRE_DISPATCH,
        GateIdOnDispatchPre.CARPACCIO_SLICE_GATE,
    ]


@then("the invocation log records verify-readiness-pre-dispatch only")
def then_invocation_log_records_readiness_only(multi_gate_composition) -> None:
    assert multi_gate_composition.last_invocation_log() == [
        GateIdOnDispatchPre.VERIFY_READINESS_PRE_DISPATCH
    ]


@then(
    "the invocation log records verify-readiness-pre-dispatch followed by "
    "carpaccio-slice-gate"
)
def then_invocation_log_records_readiness_followed_by_carpaccio(
    multi_gate_composition,
) -> None:
    assert multi_gate_composition.last_invocation_log() == [
        GateIdOnDispatchPre.VERIFY_READINESS_PRE_DISPATCH,
        GateIdOnDispatchPre.CARPACCIO_SLICE_GATE,
    ]


@then("the invocation log records carpaccio-slice-gate only")
def then_invocation_log_records_carpaccio_only(multi_gate_composition) -> None:
    assert multi_gate_composition.last_invocation_log() == [
        GateIdOnDispatchPre.CARPACCIO_SLICE_GATE
    ]
