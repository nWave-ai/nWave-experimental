"""Step methods for slice-04 — the rescoped migration gate still bites (AT-10).

Negative control / Earned-Trust probe for the slice-04 AT-07/08 rescope. The
rescoped scan excludes no-subcommand modules (P2) and sanctioned-SUT callsites
(P3); AT-10 proves it is NOT vacuously green by planting an unmarked,
concrete, registered-subcommand module-form invocation in a non-test authoring
file and asserting the rescoped scan STILL reports it.

Mandate-12 criterion 3: every step body has ≤ 2 statements, the last is a
delegation to `composition.<method>(...)`; all business logic lives in
`composition.py`. Then bodies make assertions over the returned observable.

Pillar 1: step names speak the domain (non-test authoring file, unmarked
module-form invocation, registered subcommand, rescoped migration scan,
reports … as a violation). NO technical jargon (no "regex", "rglob",
"_REGISTRY", "sentinel"). Technical detail lives behind the composition method.

Pillar 2: chained narrative — the scenario reuses the Background's
`Given_the_nwave_runtime_is_installed` from steps_slice_01 (the `installed_runtime`
composition root), then plants the synthetic violation, scans, and asserts.

Mandate 9 + 11: layer 3 filesystem scan — example-only, NO PBT machinery. AT-10
is a single concrete-example negative control over a synthetic fixture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, then, when


if TYPE_CHECKING:
    from pathlib import Path

    from .composition import DesCliComposition


# Feature binding lives in `../test_slice_04_gate_non_vacuity.py` — that binder
# calls `scenarios(...)` after the pytest config stack is active.


# ---- Given --------------------------------------------------------------


@given(
    "a non-test authoring file carries an unmarked module-form invocation of a "
    "registered subcommand",
    target_fixture="authoring_root",
)
def given_a_non_test_authoring_file_carries_an_unmarked_invocation(
    installed_runtime: DesCliComposition,
    tmp_path: Path,
) -> Path:
    # `roadmap` is a registered subcommand (registry SSOT) → P2 holds; the
    # planted line is concrete (P1) and carries no sanction sentinel (P3✗).
    return installed_runtime.plant_unmarked_module_form_invocation(tmp_path, "roadmap")


# ---- When ---------------------------------------------------------------


@when(
    "the rescoped migration scan inspects that authoring file",
    target_fixture="violation_hits",
)
def when_the_rescoped_migration_scan_inspects_that_authoring_file(
    installed_runtime: DesCliComposition,
    authoring_root: Path,
) -> tuple[tuple[str, int, str], ...]:
    return installed_runtime.scan_directory_for_unmarked_registered_module_form(
        authoring_root
    )


# ---- Then ---------------------------------------------------------------


@then(
    "the rescoped migration scan reports the unmarked registered-subcommand "
    "invocation as a violation"
)
def then_the_rescoped_scan_reports_the_unmarked_invocation_as_a_violation(
    violation_hits: tuple[tuple[str, int, str], ...],
) -> None:
    assert violation_hits != (), (
        "AT-10 non-vacuity: the rescoped migration scan must STILL flag an "
        "unmarked, concrete, registered-subcommand module-form invocation. It "
        "reported ZERO hits over a fixture that plants exactly one such "
        "violation — the rescope has gone vacuously green (an over-broad "
        "exclusion would now pass undetected)."
    )
    assert any(
        "des.cli.roadmap" in line for _relpath, _lineno, line in violation_hits
    ), (
        "AT-10 non-vacuity: the rescoped scan reported hits, but none name the "
        "planted `des.cli.roadmap` registered-subcommand invocation. Reported "
        f"hits: {violation_hits}"
    )
