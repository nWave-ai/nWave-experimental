"""pytest-bdd binding for f-declarative-gate-composition slice-02 (iterator contract).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
flavor_dispatcher.dispatch_lifecycle_event + resolve_wave_gate_stack seams over a
real flavor file with a real in-process gate_invoker Port. Step bodies delegate to
the composition root; no business logic in step bodies (Mandate-12). The <first>/
<second>/<gate_id>/<flavor> parameters parametrize the reorder positions, the
uncatalogued-gate cases, and the shipped flavors.

Active-RED scaffold (atdd_pure -- NOT @skip): every scenario is RED until DELIVER
ships resolve_wave_gate_stack + the generic per-wave dispatch path that carries the
verdict + recovery and fails closed on an uncatalogued gate. Each case fails with a
semantic AssertionError naming the missing seam, never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02_iterator_contract import IteratorContractComposition


scenarios("../slice-02-iterator-contract.feature")


@pytest.fixture
def iterator() -> IteratorContractComposition:
    return IteratorContractComposition()


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse("a DISCUSS gate-in stack declared in the order {first} then {second}")
)
def given_reorderable_stack(
    iterator: IteratorContractComposition,
    first: str,
    second: str,
    tmp_path: Path,
) -> None:
    iterator.given_reorderable_stack(tmp_path, first, second)


@given(
    parsers.parse("the declared composition carries the uncatalogued gate id {gate_id}")
)
def given_stack_declares_uncatalogued_gate(
    iterator: IteratorContractComposition, gate_id: str, tmp_path: Path
) -> None:
    iterator.given_stack_declares_uncatalogued_gate(tmp_path, gate_id)


@given(
    parsers.parse(
        "the declared composition carries the gate {gate_id} whose mechanism cannot run"
    )
)
def given_gate_mechanism_cannot_run(
    iterator: IteratorContractComposition, gate_id: str, tmp_path: Path
) -> None:
    iterator.given_gate_mechanism_cannot_run(tmp_path, gate_id)


@given(parsers.parse("the shipped flavor {flavor}"))
def given_shipped_flavor(iterator: IteratorContractComposition, flavor: str) -> None:
    iterator.given_shipped_flavor(flavor)


# --- When ------------------------------------------------------------------


@when("the declared stack is iterated")
def when_declared_stack_is_iterated(iterator: IteratorContractComposition) -> None:
    iterator.when_declared_stack_is_iterated()


@when("the unknown gate is iterated")
def when_unknown_gate_is_iterated(iterator: IteratorContractComposition) -> None:
    iterator.when_unknown_gate_is_iterated()


@when("the indeterminate gate is iterated")
def when_indeterminate_gate_is_iterated(
    iterator: IteratorContractComposition,
) -> None:
    iterator.when_indeterminate_gate_is_iterated()


@when("the shipped event compositions are resolved")
def when_shipped_event_compositions_are_resolved(
    iterator: IteratorContractComposition,
) -> None:
    iterator.when_shipped_event_compositions_are_resolved()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the gate {first} vetoes first"))
def then_first_declared_gate_vetoes_first(
    iterator: IteratorContractComposition, first: str
) -> None:
    iterator.then_first_declared_gate_vetoes_first()


@then("the uncatalogued gate fails closed and is named")
def then_unknown_gate_fails_closed_named(
    iterator: IteratorContractComposition,
) -> None:
    iterator.then_unknown_gate_fails_closed_named()


@then("the indeterminate gate degrades loud")
def then_indeterminate_degrades_loud(
    iterator: IteratorContractComposition,
) -> None:
    iterator.then_indeterminate_degrades_loud()


@then("the shipped event compositions iterate unchanged")
def then_shipped_event_compositions_unregressed(
    iterator: IteratorContractComposition,
) -> None:
    iterator.then_shipped_event_compositions_unregressed()
