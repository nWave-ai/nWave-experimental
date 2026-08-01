"""Step definitions: a broken telemetry filesystem must refuse loudly.

unified-event-store slice-02 (DD-14, EXP-unified-event-store-1).

Layer 1 walking-skeleton (subprocess, terminal-wiring facet) + Layer 2
in-process (Mandate 13 L2 default, content facet). Example-only, no PBT
machinery (Mandate 11 -- sad paths at this layer stay example-based); the
Scenario Outline's 3 rows ARE the enumeration of the charter's own fault
matrix.

Step bodies delegate to `EventStoreProbeComposition`; no inline business
logic (Mandate-12 criterion 3).

active-RED scaffold (atdd_pure -- NOT `@skip`). At HEAD
`UnifiedEventStoreAdapter` / `StoreAvailabilityProbe` are DISTILL-authored
scaffolds whose methods raise a bare `AssertionError` -- every scenario below
fails for that reason today, a semantic `AssertionError`, never a
collection/import error (the composition catches it narrowly and records it
on the observable).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import EventStoreProbeComposition


scenarios("../slice-02-startup-refusal.feature")


@pytest.fixture
def composition() -> Iterator[EventStoreProbeComposition]:
    """Production-wired composition root driving the real event-store-probe CLI."""
    root = EventStoreProbeComposition()
    try:
        yield root
    finally:
        root.restore_permissions()


# --- Given ---------------------------------------------------------------


@given("the store operator has a real repo with a healthy telemetry substrate")
def given_healthy_sandbox(
    composition: EventStoreProbeComposition, tmp_path: Path
) -> None:
    composition.given_healthy_sandbox(tmp_path)


@given(parsers.parse("the store operator's telemetry substrate {fault}"))
def given_fault_induced(
    composition: EventStoreProbeComposition, tmp_path: Path, fault: str
) -> None:
    composition.given_healthy_sandbox(tmp_path)
    composition.given_fault_induced(fault)


# --- When ------------------------------------------------------------------


@when("the store operator runs the real des event-store-probe command against it")
def when_run_via_subprocess(composition: EventStoreProbeComposition) -> None:
    composition.when_run_via_subprocess()


@when(
    "the store operator runs the event store probe in-process against the "
    "real des CLI entry"
)
def when_run_in_process(composition: EventStoreProbeComposition) -> None:
    composition.when_run_in_process()


# --- Then --------------------------------------------------------------------


@then("the probe command is discoverable through des --help")
def then_discoverable(composition: EventStoreProbeComposition) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "des.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "event-store-probe" in result.stdout, (
        "the event-store-probe subcommand must be listed on `des --help` "
        f"(the store operator's discovery surface) -- got: {result.stdout!r}"
    )


@then("the probe reports success with exit code zero")
def then_success(composition: EventStoreProbeComposition) -> None:
    obs = composition.observable()
    assert obs.exit_code == 0, (
        "a healthy telemetry substrate must produce exit code 0 -- "
        f"{composition.diag()}"
    )


@then("the probe refuses with a non-zero exit code")
def then_refuses(composition: EventStoreProbeComposition) -> None:
    obs = composition.observable()
    assert obs.exit_code is not None and obs.exit_code != 0, (
        "a broken telemetry substrate must never exit 0 -- the store must "
        f"refuse loudly instead of reporting success. {composition.diag()}"
    )


@then("the refusal names WHAT failed, WHY it matters, and HOW to fix it")
def then_what_why_how(composition: EventStoreProbeComposition) -> None:
    text = composition.observable().captured_output
    assert "WHAT" in text and "WHY" in text and "HOW" in text, (
        "the refusal must teach the operator WHAT failed, WHY it matters, "
        f"and HOW to fix it -- reading only the terminal. {composition.diag()}"
    )


@then("the refusal names a path inside the store operator's own sandbox")
def then_names_sandbox_path(composition: EventStoreProbeComposition) -> None:
    """Structural containment (peer-review MEDIUM finding, closed): a
    substring check (`sandbox in text`) is satisfied by a sibling-prefix
    collision -- sandbox `/tmp/abc` is "contained" in a decoy path
    `/tmp/abc-decoy/telemetry` -- while genuine containment is violated.
    Mirrors `test_unified_event_store_adapter.py`'s
    `test_refusal_path_is_structurally_inside_the_given_project_root`,
    which already asserts this the strong way via `Path.relative_to`; this
    Gherkin AT is the higher-stakes layer (drives the real CLI end-to-end)
    and must not use the weaker check on the identical property."""
    import json

    sandbox = composition.sandbox_root()
    text = composition.observable().captured_output

    refused_path: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "path" in payload:
            refused_path = payload["path"]
            break

    assert refused_path is not None, (
        "the refusal must emit a machine-readable JSON line carrying a "
        f"'path' field -- none was captured. {composition.diag()}"
    )
    try:
        Path(refused_path).relative_to(sandbox)
    except ValueError:
        pytest.fail(
            f"the refusal's path {refused_path!r} is NOT structurally "
            f"inside the sandbox {sandbox!r} -- a substring match would "
            "wrongly pass a sibling-prefix decoy (e.g. sandbox '/tmp/abc' "
            "vs refused '/tmp/abc-decoy/telemetry'); a path outside the "
            "sandbox means the store fell back to a different substrate, "
            f"which is worse than refusing. {composition.diag()}"
        )


@then("nothing is written under the sandbox's telemetry root")
def then_nothing_written(composition: EventStoreProbeComposition) -> None:
    from tests.common.state_delta import assert_state_delta, unchanged

    assert_state_delta(
        before={"telemetry_root.listing": composition.telemetry_root_listing_before()},
        after={"telemetry_root.listing": composition.telemetry_root_listing()},
        universe={"telemetry_root.listing"},
        expected={"telemetry_root.listing": unchanged()},
    )


@then("the sandbox's telemetry root is left with the same entries it started with")
def then_no_residue(composition: EventStoreProbeComposition) -> None:
    from tests.common.state_delta import assert_state_delta, unchanged

    assert_state_delta(
        before={"telemetry_root.listing": composition.telemetry_root_listing_before()},
        after={"telemetry_root.listing": composition.telemetry_root_listing()},
        universe={"telemetry_root.listing"},
        expected={"telemetry_root.listing": unchanged()},
    )
