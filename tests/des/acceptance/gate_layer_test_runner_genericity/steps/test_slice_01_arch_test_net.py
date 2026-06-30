"""Step definitions for gate-layer-test-runner-genericity slice-01 (Mandate-12).

slice-01 (the arch-test net) -- a stdlib-only static scan over nWave's OWN
gate/wave source tree (`src/des/`) that ALLOWLISTS the two legitimate
interpreter-resolution boundaries and FAILS LOUD on any other `python_for(` call
in gate/wave LOGIC.

ACTIVE-RED at HEAD (fail-for-right-reason): the scan finds the FIVE current leaks
(verified-from-source via tsunami `callers_of python_for`, binding-resolved:
run_contract_gate.py:{228,372,682}, verify_deliver_entry_contract.py:321,
verify_environmental_e2e.py:235), so the first scenario's
`Then the net refuses to pass while any hardcoded interpreter-resolution remains`
fires a semantic `AssertionError` naming every offending file:line. This is RED,
NOT BROKEN: the test collects (module top imports only the scan composition +
domain types -- no not-yet-implemented production module), and the assertion is
reached and fails because the leaks EXIST. Once DELIVER reroutes all five leaks
through `RunnerAdapter` (the same slice-01 net + class-fix scope), the scan
returns an empty leak list and the net goes GREEN. The ATs are NOT xfail-marked:
the dispatch requires RED-for-right-reason to be directly observable.

Step bodies delegate to `GateLayerScan` -- no inline business logic (Mandate-12
criterion 3: <=2 statements, final = composition.<method>(...), no control flow).
Domain nouns are typed via `domain_types_slice_01` (criterion 1); the composition
service signatures consume those typed parameters (criterion 2).

Mandate-13: the SUT is the real static scan over the REAL `src/des/` tree (the
scan IS the Layer-4 driving port). Mandate-9/11: a layer-4 static scan over a
fixed tree is example-only -- the leak set is an enumerable fact about HEAD, not
an unbounded input space, so there is NO paired PBT (a property over a constant
tree would be vacuous).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_01 import GateLayerScan, ScanRootEmpty
from .domain_types_slice_01 import ALLOWLIST, ALLOWLIST_RATIONALE


scenarios("../slice-01-arch-test-net.feature")


@pytest.fixture
def scan() -> GateLayerScan:
    """The static-scan driving port over the REAL src/des/ gate/wave tree."""
    return GateLayerScan()


# A per-scenario bag carrying the scan result (or the raised fail-closed error)
# from the When to the Then. A plain dict keeps step bodies <=2 statements.
@pytest.fixture
def outcome() -> dict[str, object]:
    return {}


# ===========================================================================
# Given
# ===========================================================================


@given("the gate and wave source layer")
def _given_real_gate_layer(scan: GateLayerScan) -> None:
    """The REAL `src/des/` tree -- the scan's default root (no setup needed)."""
    assert scan.scanned_root.is_dir(), (
        f"the gate/wave source root {scan.scanned_root} does not exist -- "
        "the arch net cannot scan a tree that is not there"
    )


@given("a gate and wave source layer that resolves to no source files")
def _given_empty_source_layer(scan: GateLayerScan, tmp_path: Path) -> None:
    """Point the scan at an EMPTY tree -- the anti-vacuity fail-closed case."""
    scan.scanned_root = tmp_path  # zero .py files under here


# ===========================================================================
# When
# ===========================================================================


@when("the architecture net scans it for interpreter-resolution outside the allowlist")
def _when_net_scans(scan: GateLayerScan, outcome: dict[str, object]) -> None:
    """Drive the real static scan; capture leaks OR the fail-closed error."""
    try:
        outcome["leaks"] = scan.find_interpreter_leaks()
    except ScanRootEmpty as exc:  # fail-closed anti-vacuity path
        outcome["fail_closed"] = exc


# ===========================================================================
# Then
# ===========================================================================


@then("the net reports every hardcoded interpreter-resolution site by file and line")
def _then_reports_sites(outcome: dict[str, object]) -> None:
    """Each leak carries a `<file>:<line>` site -- the live leak inventory."""
    leaks = outcome["leaks"]
    assert all(":" in leak.site and leak.line > 0 for leak in leaks), (
        "every reported leak must carry a file:line site so the failure doubles "
        f"as the live leak inventory (leaks: {[leak.site for leak in leaks]})"
    )


@then(
    "the net refuses to pass while any interpreter-resolution leak remains "
    "outside the allowlist"
)
def _then_refuses_while_leaks_remain(outcome: dict[str, object]) -> None:
    """ACTIVE-RED keystone: the gate/wave layer must hold ZERO leaks.

    RED at HEAD -- the five current leaks exist, so this fires a semantic
    AssertionError naming every offending file:line. GREEN once DELIVER reroutes
    all five leaks through `RunnerAdapter` (same slice-01 net + class-fix scope).
    """
    leaks = outcome["leaks"]
    inventory = "\n  ".join(f"{leak.site}  ->  {leak.snippet}" for leak in leaks)
    assert not leaks, (
        f"{len(leaks)} hardcoded interpreter-resolution site(s) found in the "
        "gate/wave layer OUTSIDE the allowlist -- gate LOGIC must route through the "
        "runner registry / RunnerAdapter, never call `python_for(` directly "
        "(a non-python target would be denied a genuine SliceCommitVerified):\n  "
        f"{inventory}"
    )


@then("the interpreter port and the python run-facet are exempt from the net")
def _then_boundaries_exempt(outcome: dict[str, object]) -> None:
    """No allowlisted boundary file appears among the reported leaks."""
    leak_files = {Path(leak.file).as_posix() for leak in outcome["leaks"]}
    assert not any(allowed in lf for lf in leak_files for allowed in ALLOWLIST), (
        "an allowlisted legitimate boundary was reported as a leak -- the "
        f"interpreter port / python run-facet must be exempt (leaks: {leak_files})"
    )


@then("each exempt boundary carries a one-line rationale a reviewer can read")
def _then_rationale_present() -> None:
    """Every allowlisted boundary states WHY it is exempt (reviewer-readable)."""
    assert all(ALLOWLIST_RATIONALE.get(b, "").strip() for b in ALLOWLIST), (
        f"each allowlisted boundary needs a non-empty rationale: {ALLOWLIST_RATIONALE}"
    )


@then("the net refuses to report a clean result it never actually earned")
def _then_fail_closed(outcome: dict[str, object]) -> None:
    """Anti-vacuity: an empty scan root RAISES, never returns an empty clean list."""
    assert isinstance(outcome.get("fail_closed"), ScanRootEmpty), (
        "scanning a tree with zero source files must FAIL CLOSED (raise "
        "ScanRootEmpty), never silently return an empty leak list that reads as "
        f"'clean' (outcome: {outcome})"
    )
