"""Step definitions + scenario binder for dor-items-ssot slice-04 (the drift gate).

Tier A (Gojko-style, production composition root, example-only -- Mandate 10):
the maintainer runs the REAL ``scripts/cli/check_dor_items_drift.py`` standalone
as a subprocess (Layer 3 subprocess, Mandate-13 driving-port-only -- the SAME
driving-surface class slices 01-03 established with ``read_dor_items.py``).

slice-04 (the FINAL slice) ships the drift gate: a maintainer who edits any
Definition-of-Ready home is mechanically stopped when a home's item-list diverges
from the one authoritative place (DISCUSS K2/K3 / DESIGN DDD-5).

Read-only universe (Mandate 8): the divergent-home AT points the gate at a TMP
FIXTURE home (written under ``tmp_path``, enumerating eight items vs the
authoritative nine) + a tmp authoritative set, so the REAL repo homes are never
mutated. The consistent-state AT runs the gate over the REAL reconciled tree (no
overrides) asserting it accepts every home. The gate's declared mutation set is
stdout + exit code ONLY (DESIGN contract-shape table) -- @contract-shape
:bounded-change.

Pillar 1: domain language only -- "maintainer", "Definition-of-Ready home",
"readiness items", "authoritative set", "drift check", "refuses", "diverged". No
CLI / subprocess / YAML / JSON / exit-code jargon in the Gherkin or step names;
the gate mechanics live in the composition root only.

Pillar 2 (chained narrative): scenario 3's ``Given a Definition-of-Ready home
that lists eight readiness items ...`` reuses scenario 1's Given step-method (same
fixture build), and its ``When the maintainer runs ... over that home`` reuses
scenario 1's When step-method (same composition call) -- not a copy-pasted
fixture.

Mandate-12 (no business logic in steps): every step body delegates to the
``DorItemsDriftGateComposition`` service / a fixture-builder helper, or asserts on
the typed ``DriftReport`` observable it returns -- no control flow, no inline gate
logic.

S1 step-text uniqueness: every ``@given/@when/@then`` literal here is distinct
from slice-01..03 literals in the same feature directory -- slice-04 says "drift
check", "diverged from the authoritative set", "reconciled homes", which no
sibling declares. No cross-file shadow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_04 import DorItemsDriftGateComposition
from .domain_types_slice_04 import (
    AUTHORITATIVE_ITEM_COUNT,
    DRIFT_VERDICT_FAIL,
    DRIFT_VERDICT_PASS,
    DriftReport,
)


scenarios("../slice-04-home-drift-gate.feature")


# The authoritative set fixture: a minimal SSOT carrying exactly the nine
# canonical readiness items (the count the gate measures each home against). The
# eight-item home fixture deliberately enumerates one fewer -- the live AD-55
# drift shape -- so the gate must name it as diverged.
_AUTHORITATIVE_SET_YAML = (
    'version: "1.0.0"\n\nitems:\n'
    + "".join(
        f"  - readiness item {n}\n" for n in range(1, AUTHORITATIVE_ITEM_COUNT + 1)
    )
    + "\nhard_gates:\n  - job-traceability\n"
)

_EIGHT_ITEM_HOME_MARKDOWN = (
    "# A Definition-of-Ready home\n\n"
    "## Definition of Ready Checklist (8 Items - Hard Gate)\n\n"
    "Stories pass ALL 8 items before proceeding to DESIGN wave.\n\n"
) + "".join(f"{n}. readiness item {n}\n" for n in range(1, 9))


@pytest.fixture
def gate_composition() -> DorItemsDriftGateComposition:
    return DorItemsDriftGateComposition()


@given(
    "a Definition-of-Ready home that lists eight readiness items "
    "while the authoritative set carries nine",
    target_fixture="diverged_home_fixture",
)
def given_eight_item_home_vs_nine_authoritative(
    tmp_path: Path,
) -> tuple[Path, tuple[Path, ...]]:
    # Precondition only (read-only universe, Mandate 8): write a tmp authoritative
    # set (nine items) + a tmp home enumerating eight, so the gate can be driven
    # over the divergent fixture WITHOUT touching the real repo homes.
    ssot_path = tmp_path / "authoritative-set.yaml"
    ssot_path.write_text(_AUTHORITATIVE_SET_YAML, encoding="utf-8")
    home_path = tmp_path / "eight-item-home.md"
    home_path.write_text(_EIGHT_ITEM_HOME_MARKDOWN, encoding="utf-8")
    return ssot_path, (home_path,)


@when(
    "the maintainer runs the Definition-of-Ready drift check over that home",
    target_fixture="drift_report",
)
def when_maintainer_runs_drift_check_over_that_home(
    gate_composition: DorItemsDriftGateComposition,
    diverged_home_fixture: tuple[Path, tuple[Path, ...]],
) -> DriftReport:
    ssot_path, home_paths = diverged_home_fixture
    return gate_composition.check_homes(ssot_path, home_paths)


@when(
    "the maintainer runs the Definition-of-Ready drift check over the reconciled homes",
    target_fixture="drift_report",
)
def when_maintainer_runs_drift_check_over_reconciled_homes(
    gate_composition: DorItemsDriftGateComposition,
) -> DriftReport:
    return gate_composition.check_real_homes()


@then(
    "the drift check refuses the home and names it as diverged from the authoritative set"
)
def then_drift_check_refuses_and_names_home(
    drift_report: DriftReport,
    diverged_home_fixture: tuple[Path, tuple[Path, ...]],
) -> None:
    _, home_paths = diverged_home_fixture
    diverged_home = home_paths[0]
    assert drift_report.verdict == DRIFT_VERDICT_FAIL
    assert any(str(diverged_home) in named for named in drift_report.diverged_homes)


@then("the drift check accepts every home as agreeing with the authoritative set")
def then_drift_check_accepts_every_home(
    drift_report: DriftReport,
) -> None:
    # The consistent-state AT runs over the REAL reconciled tree: on GREEN every
    # enumerated home agrees with the authoritative set, so the gate accepts with
    # no diverged homes. (Anti-vacuity pair: a naive always-FAIL gate fails here,
    # a naive always-PASS gate fails the divergent-home AT -- the pair
    # discriminates.)
    assert drift_report.verdict == DRIFT_VERDICT_PASS
    assert drift_report.diverged_homes == ()


@then("the drift check confirms it examined every canonical Definition-of-Ready home")
def then_drift_check_examined_every_canonical_home(
    drift_report: DriftReport,
) -> None:
    # Discovery-coverage guard (AT-review dimension-5 fix): a PASS verdict with an
    # empty ``diverged_homes`` is only trustworthy if the gate ACTUALLY traversed
    # every canonical count-stating home. An under-discovering GREEN (one that
    # silently inspects fewer count-stating homes than exist -- e.g. misses its OWN
    # primary transcription target nw-dor-validation/SKILL.md, or skips
    # nw-product-owner / nw-product-owner-reviewer) would report PASS vacuously;
    # asserting the gate's ``checked_homes`` covers every required home (the
    # DESIGN-pinned count-stating set) closes that hole. The coverage gap is the
    # typed observable the report exposes.
    assert drift_report.required_homes_not_examined() == ()


@then(
    "the drift check reports a refusing verdict, the diverged home, "
    "and the authoritative item count"
)
def then_drift_check_reports_structured_shape(
    drift_report: DriftReport,
    diverged_home_fixture: tuple[Path, tuple[Path, ...]],
) -> None:
    # Closed-token structured shape (Mandate 9/11 example-only): the gate reports
    # the refusing verdict token, the diverged home named in the structured
    # ``diverged_homes`` field, AND the authoritative item count it measured
    # against -- a maintainer reads the WHY (which home, against what count), not
    # a bare exit status.
    _, home_paths = diverged_home_fixture
    diverged_home = home_paths[0]
    assert drift_report.verdict == DRIFT_VERDICT_FAIL
    assert any(str(diverged_home) in named for named in drift_report.diverged_homes)
    assert drift_report.ssot_item_count == AUTHORITATIVE_ITEM_COUNT
