"""Step definitions: the slice-03 enforcement levers driven IN-PROCESS.

at-in-process-port-default slice-03 (DISCUSS US-03 Metà-B, DESIGN §3 the 6 levels
-> 6 mechanical gates + the subprocess-overuse gate + the L3/L4 enumeration
procedure + DDD-1/DDD-2b/DDD-9 degrade-LOUD / target-aware / git-free).

Layer 3 (in-process composition acceptance). Example-only, no PBT machinery
(Mandate 9/11): each lever pins a single closed observable (the structured flag
the gate emits). The sad paths (non-Python target, unrecognized language) are
enumerated explicitly (Mandate 11).

The levers are driven through the REAL gate ``main(argv)`` entries IN-PROCESS (a
direct call --- NO ``subprocess.run([sys.executable, ...])`` fork). This honours
THIS feature's own Locked Decision (subprocess reserved for @walking_skeleton);
the slice-03 ATs are the proof the levers can be driven in-process.

Step bodies delegate to ``EnforcementLeverComposition``; no inline business logic
(Mandate-12 criterion 3) --- each body is a typed accessor plus a composition call.

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD the gates ship NO lever-1
wiring / L3 / L4 invariant, NO ZOMBIES-zero floor, NO coverage-on-executed-path
lever, NO per-language spawn-detector flag surface, NO target-aware F821 re-wire.
So every observable assertion RED-fails for the right reason (the lever's flag
does not fire / the NOT_APPLICABLE reason is absent). DELIVER ships the levers to
turn these GREEN. Collection imports ONLY the three stable ``main`` entries
(present) --- the absent lever names appear nowhere at module top, so the suite
COLLECTS cleanly (DESIGN P1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_03 import EnforcementLeverComposition
from .domain_types_slice_03 import GateVerdict


scenarios("../slice-03-enforcement-levers.feature")


@pytest.fixture
def lever() -> EnforcementLeverComposition:
    """Production-wired composition root driving the real gate entries in-process."""
    return EnforcementLeverComposition()


# --- Given -------------------------------------------------------------------


@given("the maintainer has a real repo the enforcement gates can run against")
def given_real_repo(lever: EnforcementLeverComposition, tmp_path: Path) -> None:
    lever.given_real_repo(tmp_path)


@given(parsers.parse('the target project is written in "{language}"'))
def given_target_language(lever: EnforcementLeverComposition, language: str) -> None:
    lever.given_target_language(language)


# --- When: drive each lever's REAL gate entry IN-PROCESS ----------------------


@when(
    "the maintainer drives the wiring lever for an entry with no callers and no "
    "readers in-process"
)
def when_drive_lever1(lever: EnforcementLeverComposition) -> None:
    lever.drive_lever1_wiring()


@when("the maintainer drives the integration-per-adapter lever in-process")
def when_drive_l3(lever: EnforcementLeverComposition) -> None:
    lever.drive_l3_adapter_integration()


@when("the maintainer drives the contract-per-port lever in-process")
def when_drive_l4(lever: EnforcementLeverComposition) -> None:
    lever.drive_l4_port_contract()


@when("the maintainer drives the coverage-on-executed-path lever in-process")
def when_drive_lever3(lever: EnforcementLeverComposition) -> None:
    lever.drive_lever3_coverage()


@when(
    "the maintainer drives the sad-path-floor lever for a slice with no error-path "
    "test in-process"
)
def when_drive_zombies(lever: EnforcementLeverComposition) -> None:
    lever.drive_zombies_zero()


@when("the maintainer drives the undefined-name lever in-process")
def when_drive_lever2(lever: EnforcementLeverComposition) -> None:
    lever.drive_lever2_f821()


@when(
    "the maintainer drives the spawn-overuse detector for a non-walking-skeleton "
    "test that spawns a process in-process"
)
def when_drive_spawn_detector_non_ws(lever: EnforcementLeverComposition) -> None:
    lever.drive_spawn_detector(lever._target_language, walking_skeleton=False)


@when(
    "the maintainer drives the spawn-overuse detector for a walking-skeleton test "
    "that spawns a process in-process"
)
def when_drive_spawn_detector_ws(lever: EnforcementLeverComposition) -> None:
    lever.drive_spawn_detector(lever._target_language, walking_skeleton=True)


# --- Then: lever-1 wiring -----------------------------------------------------


@then("the wiring lever flags the unwired entry")
def then_lever1_flags(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert obs.flagged, (
        "the wiring lever must FLAG a produced entry reached by no real dispatch "
        "(callers==0 AND reads==0, the HARDENED OR) --- but at HEAD the readiness "
        "gate ships no `unwired_entry` invariant, so it clears where it should "
        f"refuse. {lever.diag()}"
    )


@then("the wiring lever emits its structured flag event on the captured output")
def then_lever1_event(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert obs.structured_event == "UnwiredEntryFlagged", (
        "the wiring lever must FLAG with a STRUCTURED EVENT on the captured output "
        "(Q3: a machine-readable token, never a bare exit code) --- but at HEAD no "
        f"such event is emitted. {lever.diag()}"
    )


@then("the wiring lever carries the code-fact confidence label with its flag")
def then_lever1_confidence(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert obs.confidence in {"binding-resolved", "approx", "noisy"}, (
        "the wiring lever must carry the CodeFactPort confidence label with its "
        "flag (DESIGN R6 degrade-LOUD: binding-resolved/approx GATES, noisy "
        "ADVISES) --- but at HEAD no confidence label is surfaced. "
        f"{lever.diag()}"
    )


@then("the wiring lever drove the gate without forking an interpreter")
def then_lever1_no_fork(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert not obs.forked_interpreter, (
        "the wiring lever must drive the gate `main(argv)` IN-PROCESS with no "
        "interpreter fork (this feature's own dog food) --- a forked observable "
        f"means the AT regressed to subprocess-e2e. {lever.diag()}"
    )


# --- Then: L3 integration-per-adapter ----------------------------------------


@then("the integration-per-adapter lever flags the untested adapter")
def then_l3_flags(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert obs.flagged, (
        "the integration-per-adapter lever must FLAG a driven adapter with no "
        "@real-io @adapter-integration test and no cited waiver --- but at HEAD "
        "the readiness gate ships no `integration_per_adapter` invariant. "
        f"{lever.diag()}"
    )


@then(
    "the integration-per-adapter lever emits its structured flag event on the "
    "captured output"
)
def then_l3_event(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert obs.structured_event == "AdapterIntegrationMissing", (
        "the integration-per-adapter lever must FLAG with a structured event "
        f"naming the untested adapter --- absent at HEAD. {lever.diag()}"
    )


@then("the integration-per-adapter lever drove the gate without forking an interpreter")
def then_l3_no_fork(lever: EnforcementLeverComposition) -> None:
    assert not lever.observable().forked_interpreter, (
        "the integration-per-adapter lever must drive in-process, no fork. "
        f"{lever.diag()}"
    )


# --- Then: L4 contract-per-port ----------------------------------------------


@then("the contract-per-port lever flags the uncontracted port")
def then_l4_flags(lever: EnforcementLeverComposition) -> None:
    assert lever.observable().flagged, (
        "the contract-per-port lever must FLAG a port with methods, no contract "
        "test, no cited waiver --- but at HEAD the readiness gate ships no "
        f"`contract_per_port` invariant. {lever.diag()}"
    )


@then(
    "the contract-per-port lever emits its structured flag event on the captured output"
)
def then_l4_event(lever: EnforcementLeverComposition) -> None:
    assert lever.observable().structured_event == "PortContractMissing", (
        "the contract-per-port lever must FLAG with a structured event naming the "
        f"uncontracted port --- absent at HEAD. {lever.diag()}"
    )


@then("the contract-per-port lever drove the gate without forking an interpreter")
def then_l4_no_fork(lever: EnforcementLeverComposition) -> None:
    assert not lever.observable().forked_interpreter, (
        f"the contract-per-port lever must drive in-process, no fork. {lever.diag()}"
    )


# --- Then: lever-3 coverage-on-executed-path ----------------------------------


@then("the coverage-on-executed-path lever flags the coverage-theater test")
def then_lever3_flags(lever: EnforcementLeverComposition) -> None:
    assert lever.observable().flagged, (
        "the coverage-on-executed-path lever must FLAG an AT whose driven entry "
        "shows zero production-line coverage (theater) --- but at HEAD "
        f"run_contract_gate.main ships no coverage lever. {lever.diag()}"
    )


@then(
    "the coverage-on-executed-path lever emits its structured flag event on the "
    "captured output"
)
def then_lever3_event(lever: EnforcementLeverComposition) -> None:
    assert lever.observable().structured_event == "CoverageOnExecutedPathFlagged", (
        "the coverage lever must FLAG with a structured event on the captured "
        f"output --- absent at HEAD. {lever.diag()}"
    )


@then(
    "the coverage-on-executed-path lever drove the gate without forking an interpreter"
)
def then_lever3_no_fork(lever: EnforcementLeverComposition) -> None:
    assert not lever.observable().forked_interpreter, (
        f"the coverage lever must drive in-process, no fork. {lever.diag()}"
    )


# --- Then: ZOMBIES-zero sad-path floor ----------------------------------------


@then("the sad-path-floor lever flags the missing sad-path coverage")
def then_zombies_flags(lever: EnforcementLeverComposition) -> None:
    assert lever.observable().flagged, (
        "the sad-path-floor (ZOMBIES-zero) lever must FLAG a slice with zero "
        "error-path ATs (target >=40% error/edge) --- but at HEAD "
        f"carpaccio_slice_gate.main ships no sad-path floor. {lever.diag()}"
    )


@then("the sad-path-floor lever emits its structured flag event on the captured output")
def then_zombies_event(lever: EnforcementLeverComposition) -> None:
    assert lever.observable().structured_event == "SadPathFloorFlagged", (
        "the sad-path-floor lever must FLAG with a structured event --- absent at "
        f"HEAD. {lever.diag()}"
    )


@then("the sad-path-floor lever drove the gate without forking an interpreter")
def then_zombies_no_fork(lever: EnforcementLeverComposition) -> None:
    assert not lever.observable().forked_interpreter, (
        f"the sad-path-floor lever must drive in-process, no fork. {lever.diag()}"
    )


# --- Then: spawn-overuse detector ---------------------------------------------


@then("the spawn-overuse detector flags the non-walking-skeleton spawn")
def then_spawn_flags(lever: EnforcementLeverComposition) -> None:
    oc = lever.detector_outcome()
    assert oc.spawn_flagged, (
        "the spawn-overuse detector must FLAG a non-@walking_skeleton test that "
        "forks an interpreter (per-language AST detection) --- but at HEAD the "
        "spawn-lint scans src/des/** only, carves no @walking_skeleton, and "
        f"exposes no structured flag for tests/**. {lever.detector_diag()}"
    )


@then("the spawn-overuse detector drove the gate without forking an interpreter")
def then_spawn_no_fork(lever: EnforcementLeverComposition) -> None:
    oc = lever.detector_outcome()
    assert oc.verdict is not GateVerdict.INDETERMINATE, (
        "the spawn-overuse detector must run the AST scan in-process, never "
        f"degrade to INDETERMINATE on a parseable Python fixture. {lever.detector_diag()}"
    )


@then("the spawn-overuse detector did not invoke git")
def then_spawn_git_free(lever: EnforcementLeverComposition) -> None:
    oc = lever.detector_outcome()
    assert not oc.git_invoked, (
        "the spawn-overuse detector must be GIT-FREE (generality / target-machine "
        f"agnosticism --- depend only on Python). {lever.detector_diag()}"
    )


@then("the spawn-overuse detector exempts the walking-skeleton spawn from flagging")
def then_spawn_ws_exempt(lever: EnforcementLeverComposition) -> None:
    oc = lever.detector_outcome()
    assert oc.walking_skeleton_exempt and not oc.spawn_flagged, (
        "the spawn-overuse detector must EXEMPT a @walking_skeleton test that "
        "legitimately forks an interpreter (subprocess-e2e is reserved for WS) "
        "--- but at HEAD no WS-exemption surface exists, so the detector neither "
        f"recognises nor exempts the WS spawn. {lever.detector_diag()}"
    )


@then(
    "the spawn-overuse detector reports the lever as not applicable for the "
    "unrecognized language"
)
def then_spawn_not_applicable(lever: EnforcementLeverComposition) -> None:
    oc = lever.detector_outcome()
    assert oc.verdict is GateVerdict.NOT_APPLICABLE and oc.not_applicable_reason, (
        "the spawn-overuse detector must report NOT_APPLICABLE with a loud reason "
        "for an unrecognized target language (degrade-LOUD, DDD-1) --- but at HEAD "
        "no per-language detector exists, so no NOT_APPLICABLE verdict + reason is "
        f"surfaced. {lever.detector_diag()}"
    )


@then(
    "the spawn-overuse detector does not raise a false flag on the unrecognized language"
)
def then_spawn_no_false_flag(lever: EnforcementLeverComposition) -> None:
    oc = lever.detector_outcome()
    assert not oc.spawn_flagged, (
        "the spawn-overuse detector must NEVER raise a false flag on an "
        f"unrecognized language (NOT_APPLICABLE, not a false positive). {lever.detector_diag()}"
    )


# --- Then: lever-2 F821 target-aware NOT_APPLICABLE ---------------------------


@then(
    "the undefined-name lever reports the lever as not applicable for the "
    "non-python target"
)
def then_f821_not_applicable(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert obs.verdict is GateVerdict.NOT_APPLICABLE and obs.not_applicable_reason, (
        "the undefined-name (F821) lever must report NOT_APPLICABLE on a "
        "non-Python target, emitting `health.gate.f821-unavailable.indeterminate` "
        "(DDD-2b/F4: never ruff-hardcoded as a hard requirement) --- but at HEAD "
        f"no target-aware F821 re-wire exists. {lever.diag()}"
    )


@then("the undefined-name lever does not raise a false flag on the non-python target")
def then_f821_no_false_flag(lever: EnforcementLeverComposition) -> None:
    obs = lever.observable()
    assert not obs.flagged, (
        "the undefined-name lever must NEVER hard-fail a non-Python target "
        f"(NOT_APPLICABLE, not a false flag). {lever.diag()}"
    )
