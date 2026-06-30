"""Step definitions: the in-process active-RED exemplar drives the real gate entry.

at-in-process-port-default slice-01 (DISCUSS US-02 Metà-B, DESIGN §1 P1-P4 + §2
OutputPort capture contract + F1 collection-semantics premise).

Layer 3 (in-process composition acceptance). Example-only, no PBT machinery
(Mandate 9/11): the exemplar pins a single closed observable (the in-process
exemplar route is recognised + emits its in-process-routed verdict). The
falsifier-gate forbids PBT on a closed-world finite observable at this layer; the
sad path (route absent at HEAD) is enumerated explicitly (Mandate 11).

The exemplar drives the REAL ``des.cli.run_contract_gate.main(argv)`` IN-PROCESS
(a direct call --- NO ``subprocess.run([sys.executable, ...])`` fork). This is the
walking-skeleton this feature ships: it proves the in-process active-RED pattern
is executable, the keystone the other slices presume.

The exemplar has a BOUNDED-CHANGE contract (DESIGN §2): the entry reads the repo
and appends terminal output through the (to-be-injected) OutputPort; it mutates NO
repo file. The second scenario asserts that read-only contract via
``assert_state_delta`` over a port-exposed filesystem universe (Mandate 8).

Step bodies delegate to ``InProcessExemplarComposition``; no inline business logic
(Mandate-12 criterion 3) --- each body is a typed accessor plus a composition call.

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD ``main`` has signature
``main(argv)`` only (no injected OutputPort) and ``_build_parser`` defines no
``--inprocess-exemplar`` route; invoked with that flag the entry rejects it as an
unknown argument (argparse ``SystemExit(2)`` raised at RUNTIME inside the call ---
NOT a collection error). So every observable assertion RED-fails for the right
reason (missing in-process-exemplar route + OutputPort injection). DELIVER ships
the route + the OutputPort threading to turn these GREEN. Collection imports ONLY
``main`` (present) --- the absent OutputPort/CapturingOutput names appear nowhere
at module top, so the suite COLLECTS cleanly (DESIGN P1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import InProcessExemplarComposition


scenarios("../slice-01-inprocess-active-red-exemplar.feature")


@pytest.fixture
def composition() -> InProcessExemplarComposition:
    """Production-wired composition root driving the real run-contract-gate entry."""
    return InProcessExemplarComposition()


# --- Given -------------------------------------------------------------------


@given("the maintainer has a real repo the contract gate can run against")
def given_real_repo(composition: InProcessExemplarComposition, tmp_path: Path) -> None:
    composition.given_real_repo(tmp_path)


# --- When --------------------------------------------------------------------


@when(
    "the maintainer drives the real contract-gate entry in-process for the "
    "in-process exemplar"
)
def when_drive_in_process(composition: InProcessExemplarComposition) -> None:
    composition.drive_in_process_exemplar()


# --- Then --------------------------------------------------------------------


@then("the gate recognises the in-process exemplar route")
def then_route_recognised(composition: InProcessExemplarComposition) -> None:
    obs = composition.observable()
    assert obs.route_recognised, (
        "the real contract-gate entry must RECOGNISE the in-process exemplar route "
        "(--inprocess-exemplar) when driven in-process --- but at HEAD no such route "
        f"exists, so argparse rejects the flag as unknown. {composition.diag()}"
    )


@then("the gate emits an in-process-routed verdict on the captured output")
def then_routed_verdict_emitted(composition: InProcessExemplarComposition) -> None:
    obs = composition.observable()
    assert obs.routed_verdict_emitted, (
        "driving the in-process exemplar must emit the in-process-routed verdict "
        "token on the captured terminal output (the line the injected OutputPort "
        "records) --- but at HEAD the entry has no OutputPort injection and no "
        f"exemplar route, so no such verdict is produced. {composition.diag()}"
    )


@then("the exemplar drove the entry without forking an interpreter")
def then_no_fork(composition: InProcessExemplarComposition) -> None:
    obs = composition.observable()
    assert not obs.forked_interpreter, (
        "the exemplar must drive main(argv) IN-PROCESS with no interpreter fork "
        "(the whole point of the feature) --- a forked-interpreter observable means "
        f"the driving call regressed back to subprocess-e2e. {composition.diag()}"
    )


@then("the maintainer's repo is left unchanged by the in-process exemplar run")
def then_repo_unchanged(composition: InProcessExemplarComposition) -> None:
    from tests.common.state_delta import assert_state_delta, unchanged

    assert_state_delta(
        before=composition.universe_before(),
        after=composition.capture_universe(),
        universe={"repo.exists", "repo.entry_count"},
        expected={
            "repo.exists": unchanged(),
            "repo.entry_count": unchanged(),
        },
    )
