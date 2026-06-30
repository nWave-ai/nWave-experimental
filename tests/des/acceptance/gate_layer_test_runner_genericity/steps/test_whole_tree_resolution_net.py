"""Step bindings: the whole-tree resolution arch-net (ADR-FLOW-011 D7).

Layer-4 static scan over the REAL ``run_contract_gate.py`` (Mandate-13). Step
bodies delegate to ``WholeTreeResolutionScan`` -- no inline business logic
(Mandate-12 criterion 3). Domain nouns are typed via ``domain_types_whole_tree``
(criterion 1); the composition consumes those typed parameters (criterion 2).

GREEN at HEAD: all four whole-tree modes resolve a runner before any pytest leg --
``_mode_run_suite`` via the RUN router (``_maybe_route_through_runner_whole_tree``,
#73 DELIVER) and the three digest modes via the DIGEST router
(``_maybe_route_digest_through_runner``, slice-02). The scan reports zero unrouted
modes. The net still BITES: deleting a resolver call from any mode preamble flips
it RED (proven by the slice-02 mutation check), so this is not a vacuous green.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_whole_tree import ScanSubjectMissing, WholeTreeResolutionScan


scenarios("../slice-01-whole-tree-resolution-net.feature")


@pytest.fixture
def scan() -> WholeTreeResolutionScan:
    """The static-scan driving port over the REAL run_contract_gate.py source."""
    return WholeTreeResolutionScan()


@pytest.fixture
def outcome() -> dict[str, object]:
    """Carries the scan result (or the fail-closed error) from When to Then."""
    return {}


# --- Given -------------------------------------------------------------------


@given("the whole-tree contract-gate source")
def given_real_source(scan: WholeTreeResolutionScan) -> None:
    assert scan.source.is_file(), (
        f"the whole-tree contract-gate source {scan.source} does not exist -- the "
        "arch net cannot scan a module that is not there"
    )


@given("a whole-tree contract-gate source that resolves to no whole-tree modes")
def given_empty_source(scan: WholeTreeResolutionScan, tmp_path: Path) -> None:
    empty = tmp_path / "run_contract_gate.py"
    empty.write_text("def _unrelated() -> int:\n    return 0\n", encoding="utf-8")
    scan.source = empty


# --- When --------------------------------------------------------------------


@when(
    "the architecture net scans each whole-tree mode for the resolution-before-pytest "
    "ordering"
)
def when_scan(scan: WholeTreeResolutionScan, outcome: dict[str, object]) -> None:
    try:
        outcome["unrouted"] = scan.find_unrouted_modes()
    except ScanSubjectMissing as exc:  # fail-closed anti-vacuity path
        outcome["fail_closed"] = exc


# --- Then --------------------------------------------------------------------


@then(
    "the net reports every whole-tree mode that reaches a pytest-bound leg with no "
    "preceding runner resolution"
)
def then_reports_sites(outcome: dict[str, object]) -> None:
    unrouted = outcome["unrouted"]
    assert all(":" in m.site and m.leg_line > 0 for m in unrouted), (
        "every reported unrouted mode must carry a <mode>:<line> site so the failure "
        f"doubles as the live leak inventory (sites: {[m.site for m in unrouted]})"
    )


@then(
    "the net refuses to pass while any whole-tree mode reaches pytest without resolving "
    "the runner first"
)
def then_refuses_while_unrouted(outcome: dict[str, object]) -> None:
    unrouted = outcome["unrouted"]
    inventory = "\n  ".join(f"{m.site}  ->  {m.reason}" for m in unrouted)
    assert not unrouted, (
        f"{len(unrouted)} whole-tree mode(s) reach a pytest-bound leg WITHOUT a "
        "preceding whole-tree runner resolution -- each must route through a runner "
        "resolver (`_maybe_route_through_runner_whole_tree` for the run-suite mode, "
        "`_maybe_route_digest_through_runner` for the digest modes) in its preamble "
        "before any pytest leg, so a non-Python target never reaches the hardcoded "
        f"pytest seam (#73):\n  {inventory}"
    )


@then("the net refuses to report a clean result it never actually earned")
def then_fail_closed(outcome: dict[str, object]) -> None:
    assert isinstance(outcome.get("fail_closed"), ScanSubjectMissing), (
        "scanning a source with zero whole-tree modes must FAIL CLOSED (raise "
        "ScanSubjectMissing), never silently return an empty leak list that reads "
        f"as 'all modes routed' (outcome: {outcome})"
    )
