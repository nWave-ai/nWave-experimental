"""pytest-bdd binding for the contract-test isolation invariant (slice-02, AT-7).

Driving port: the production ``handle_pre_tool_use`` hook adapter invoked in-process
exactly as the shipped ``claude_code_hook_stdin`` fixture invokes it (Mandate-13
driving-port-only, Layer-3 composition). Step bodies delegate to the composition
root (``composition_slice_02.py``); no production module is imported-and-called at
the step boundary, and no business logic / control flow lives in a step body
(Mandate-12: each body is a single delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module. Each step
decorator's literal text is unique within this feature directory (S1 step-text-
uniqueness invariant).

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): at HEAD the
``claude_code_hook_stdin`` fixture takes ``tmp_path`` but never sets CWD/store-root,
so the in-process handler reads the developer's LIVE working-tree floor. Modelling
that leaky harness, the harness decision tracks the live floor instead of the
injected one, so each isolation Then fails for the right reason (semantic
``AssertionError``). slice-02 wires the injected root as the handler's CWD/store-root
-> the harness reads the injected floor -> GREEN. Each RED is a semantic
``AssertionError`` -- never a collection / import / setup error.

The witness uses TWO isolated roots derived from pytest's ``tmp_path``: a ``live``
root standing in for the developer's working tree, and an ``injected`` root the
harness is supposed to honour. They carry DIVERGING floors so a leaked live floor
is observable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02 import ContractIsolationComposition


scenarios("../slice-02-contract-test-isolation.feature")


@pytest.fixture
def composition() -> ContractIsolationComposition:
    return ContractIsolationComposition()


@pytest.fixture
def live_root(tmp_path: Path) -> Path:
    """The developer's live working tree (a leaky harness reads its floor)."""
    root = tmp_path / "live"
    root.mkdir()
    return root


@pytest.fixture
def injected_root(tmp_path: Path) -> Path:
    """The clean isolated root the harness is supposed to read its floor from."""
    root = tmp_path / "injected"
    root.mkdir()
    return root


# --- Given -------------------------------------------------------------------


@given("a non-clean wave floor is armed in the developer's live working tree")
def given_live_nonclean_floor(
    composition: ContractIsolationComposition, live_root: Path
) -> None:
    composition.given_live_nonclean_floor(live_root)


@given("the developer's live working tree has no wave floor armed")
def given_live_clean_tree(
    composition: ContractIsolationComposition, live_root: Path
) -> None:
    composition.given_live_clean_tree(live_root)


@given("the contract-test harness injects a clean isolated floor root")
def given_injected_clean_root(
    composition: ContractIsolationComposition, injected_root: Path
) -> None:
    composition.given_injected_clean_root(injected_root)


@given(parsers.parse('the contract-test harness injects an armed "{wave}" floor'))
def given_injected_armed_floor(
    composition: ContractIsolationComposition, injected_root: Path, wave: str
) -> None:
    composition.given_injected_armed_floor(injected_root, wave)


# --- When --------------------------------------------------------------------


@when("the harness validates a partial-context dispatch through the hook")
def when_harness_validates_partial_dispatch(
    composition: ContractIsolationComposition,
) -> None:
    composition.when_harness_validates_partial_dispatch()


# --- Then --------------------------------------------------------------------


@then(
    "the hook decision reflects the injected clean floor, not the live "
    "working-tree floor"
)
def then_decision_reflects_injected_clean_floor(
    composition: ContractIsolationComposition,
) -> None:
    composition.then_decision_reflects_injected_floor()


@then(
    "the hook decision reflects the injected armed floor, not the live "
    "working-tree floor"
)
def then_decision_reflects_injected_armed_floor(
    composition: ContractIsolationComposition,
) -> None:
    composition.then_decision_reflects_injected_floor()


@then("the harness decision is ALLOW")
def then_decision_is_allow(composition: ContractIsolationComposition) -> None:
    composition.then_decision_is_allow()


@then("the harness decision is BLOCK")
def then_decision_is_block(composition: ContractIsolationComposition) -> None:
    composition.then_decision_is_block()
