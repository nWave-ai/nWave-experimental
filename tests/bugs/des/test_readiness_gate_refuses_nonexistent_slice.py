"""Regression: `des verify-readiness-pre-dispatch` clears a `--slice-id` that
has NO row in the feature's Slice Plan table -- byte-identical to a real,
planned slice.

RCA: docs/feature/fix-readiness-gate-clears-on-empty/deliver/rca.md
Feature delta: docs/feature/fix-readiness-gate-clears-on-empty/feature-delta.md

Root cause (single locus, confirmed empirically): `_check_slice_plan_section`
(`src/des/cli/verify_readiness_pre_dispatch.py:214-245`) only checks that the
`## Wave: DISCUSS / [REF] Slice Plan` HEADING is present in feature-delta.md --
it never parses the table into rows nor joins on `slice_id`. Contrast: the
sibling `carpaccio-slice-gate` already discriminates correctly via
`des.cli.carpaccio_format.parse_slice_plan(...).row_for(slice_id)` (the exact
predicate this gate should reuse but does not call at all).

Bug observable (oracle, per feature-delta `[REF] Value`): a nonexistent /
scenario-less `--slice-id` (e.g. `slice-99`, no row in the Slice Plan table)
must be REFUSED -- `slice_plan_section` invariant `satisfied: false`, overall
`verdict != "cleared"` -- with a what/why/how remediation naming the slice.
A REAL slice (one that HAS a row, e.g. `slice-01`) must still clear -- this
guards against a fix that over-refuses.

Driving port (Mandate 16, no-direct-domain-testing; the exact in-process
idiom `test_verify_readiness_pre_dispatch_bugfix_lane.py` and
`test_slice_02_readiness_gate_lane_profile.py` already establish): every AT
below drives `des.cli.verify_readiness_pre_dispatch.main(argv)` -- the SAME
composition root `des verify-readiness-pre-dispatch` dispatches -- capturing
the emitted stdout JSON verdict line. No subprocess fork needed for this
CLI-JSON-shape bug; the in-process entry is the established, lighter-weight
harness idiom for this exact gate.

Fixture idiom (REUSED, not invented): mirrors
`ReadinessGateComposition.workspace_satisfying_every_invariant` in
`tests/des/acceptance/d4_phase_3_flavor_dispatcher/conftest.py` -- a hermetic
`docs/feature/{feature_id}/feature-delta.md` carrying the `[REF] Slice Plan`
heading + a ONE-row table, a `## Reuse Analysis` no-overlap exemption, and a
`## Test Reuse & Consolidation Analysis` methodology-exempt marker (so
invariants 6/7 clear without extra ceremony). No `.feature` files are
authored (invariant 2, `scenario_slice_tags`, is vacuously satisfied with
zero feature files for the id) and no AT-review ledger record is authored
(invariant 3, `at_review_verdict`, is advisory-satisfied by default --
`rigor.human_authorization` defaults to `False`, velocity-v2). A bare `.git`
directory (no real `git init`) satisfies `gate_output_produceable` -- the
SAME hermetic marker `test_verify_readiness_pre_dispatch_bugfix_lane.py` and
`test_slice_02_readiness_gate_lane_profile.py` already use; the readiness
gate has zero `git` dependency (target-machine agnosticism mandate), so a
real git repo is not required to exercise it.

RED-for-right-reason: `test_nonexistent_slice_is_refused_with_clean_remediation`
below FAILS today with a genuine semantic `AssertionError` -- the gate
reports `slice_plan_section` `satisfied: True` and `verdict: "cleared"` for
`slice-99` (no row exists), never an import/collection error.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from des.cli import verify_readiness_pre_dispatch as gate


_FEATURE_ID = "synthetic-readiness-nonexistent-slice-feature"
_REAL_SLICE_ID = "slice-01"
_NONEXISTENT_SLICE_ID = "slice-99"
_INV_SLICE_PLAN = "slice_plan_section"


def _author_feature_delta_with_one_real_slice(repo_root: Path) -> None:
    """Author a hermetic feature-delta carrying ONE real Slice Plan row
    (`slice-01`) plus the reuse-first + sustainability legs -- mirrors
    `ReadinessGateComposition.workspace_satisfying_every_invariant`
    (`tests/des/acceptance/d4_phase_3_flavor_dispatcher/conftest.py`)."""
    workspace = repo_root / "docs" / "feature" / _FEATURE_ID
    workspace.mkdir(parents=True)
    (workspace / "feature-delta.md").write_text(
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n"
        "|---|---|\n"
        f"| {_REAL_SLICE_ID} | the only planned slice |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


@pytest.fixture
def hermetic_repo(tmp_path: Path) -> Path:
    """A hermetic repo_root: a bare `.git` marker (no real `git init` --
    the gate has zero `git` dependency, target-machine agnosticism) plus a
    feature-delta carrying exactly one real Slice Plan row (`slice-01`)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    _author_feature_delta_with_one_real_slice(repo_root)
    return repo_root


def _run(repo_root: Path, slice_id: str) -> tuple[int, dict]:
    """Invoke the gate's `main(argv)` in-process and capture the emitted
    stdout JSON verdict line -- mirrors `_run` in
    `test_verify_readiness_pre_dispatch_bugfix_lane.py` verbatim."""
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--slice-id",
        slice_id,
        "--repo-root",
        str(repo_root),
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = gate.main(argv)
    line = next(
        (
            ln
            for ln in reversed(out.getvalue().splitlines())
            if ln.strip().startswith("{")
        ),
        "{}",
    )
    return code, json.loads(line)


def _invariant(report: dict, invariant_id: str) -> dict:
    for inv in report.get("invariants", []):
        if inv["id"] == invariant_id:
            return inv
    raise AssertionError(
        f"invariant {invariant_id!r} missing from report entirely -- the "
        f"gate must always emit every invariant it evaluates. observed "
        f"report={report}"
    )


# --- AT-1 (positive -- guards against over-refusal) -------------------------


def test_real_planned_slice_still_clears(hermetic_repo: Path) -> None:
    """A real slice (`slice-01`, which HAS a row in the Slice Plan table)
    must still clear once the row-existence check is added -- the fix must
    not over-refuse a legitimately planned slice.

    CONTRACT_SHAPE: bounded-change
    """
    code, report = _run(hermetic_repo, _REAL_SLICE_ID)

    assert report.get("verdict") == "cleared" and code == 0, (
        "a real, planned slice (slice-01, which HAS a Slice Plan row) must "
        f"clear. observed verdict={report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )
    slice_plan_inv = _invariant(report, _INV_SLICE_PLAN)
    assert slice_plan_inv["satisfied"] is True, (
        "the slice_plan_section invariant must be satisfied for a slice "
        f"that HAS a real row. observed={slice_plan_inv}"
    )


# --- AT-2 (core negative -- RED today, the diagnosed defect) ----------------


def test_nonexistent_slice_is_refused_with_clean_remediation(
    hermetic_repo: Path,
) -> None:
    """A `--slice-id` with NO row in the feature-delta Slice Plan table
    (`slice-99`) must be REFUSED -- `slice_plan_section` `satisfied: false`,
    overall verdict not `cleared` -- carrying a clean what/why/how
    remediation naming the slice (NOT a crash/traceback).

    RED today (RCA `deliver/rca.md`): `_check_slice_plan_section` never
    cross-references `--slice-id` against the actual Slice Plan rows -- it
    checks only that the section HEADING is present. `slice-99` (zero rows,
    zero scenarios) today reports `satisfied: True` / `verdict: "cleared"`,
    byte-identical to the real `slice-01` case above -- a false-positive
    "my preconditions are OK" an agent would wrongly consume.

    CONTRACT_SHAPE: bounded-change
    """
    code, report = _run(hermetic_repo, _NONEXISTENT_SLICE_ID)

    # Clean verdict, never a crash/traceback: the gate must always emit a
    # well-formed JSON report with the invariant present, even on refusal.
    assert isinstance(report, dict) and report.get("invariants"), (
        "the gate must emit a well-formed JSON verdict on refusal, never "
        f"crash/traceback. observed report={report}"
    )
    slice_plan_inv = _invariant(report, _INV_SLICE_PLAN)

    assert slice_plan_inv["satisfied"] is False, (
        "slice-99 has NO row in the feature-delta Slice Plan table -- the "
        "slice_plan_section invariant must be satisfied: false. THE BUG: "
        "the gate never cross-references --slice-id against the actual "
        "Slice Plan rows (it only checks the section heading is present), "
        f"so it wrongly reports satisfied: true. observed={slice_plan_inv}"
    )
    assert report.get("verdict") != "cleared" and code != 0, (
        "a slice with no Slice Plan row must not clear -- the overall "
        f"verdict must be 'refused' (exit != 0). observed verdict="
        f"{report.get('verdict')!r}, code={code}, invariants="
        f"{report.get('invariants')}"
    )

    remediation = slice_plan_inv.get("remediation") or ""
    assert remediation, (
        "the refusal must carry a what/why/how remediation on the "
        f"slice_plan_section invariant, not a bare failure. observed="
        f"{slice_plan_inv}"
    )
    assert _NONEXISTENT_SLICE_ID in remediation, (
        "the remediation must NAME the offending slice id so the operator "
        f"knows exactly what to fix. observed remediation={remediation!r}"
    )


# --- AT-3 (negative AT -- the WRONG outcome must NOT be produced) -----------


def test_bogus_slice_never_clears_like_a_real_planned_slice(
    hermetic_repo: Path,
) -> None:
    """Negative AT (evidence gate, evolution P0.3): the WRONG outcome -- a
    never-planned slice clearing byte-identical to a real one -- must NOT be
    produced. This asserts the ABSENCE of the false-positive, distinct from
    AT-2's presence-of-the-refusal shape.

    The wrong outcome the bug produces today: `slice-99` (no Slice Plan row)
    returns `verdict: "cleared"` / exit 0 / `slice_plan_section satisfied:
    True` -- identical to the real `slice-01`. This test pins that the bogus
    slice must NEVER share the real slice's cleared verdict: the two verdicts
    must DIFFER (the bug makes them identical). RED today for exactly that
    reason -- the gate produces the forbidden identical-clear outcome.

    CONTRACT_SHAPE: bounded-change
    """
    real_code, real_report = _run(hermetic_repo, _REAL_SLICE_ID)
    bogus_code, bogus_report = _run(hermetic_repo, _NONEXISTENT_SLICE_ID)

    # The forbidden outcome: a never-planned slice must NOT clear.
    assert bogus_report.get("verdict") != "cleared", (
        "the WRONG outcome (a never-planned slice clearing) must NOT be "
        f"produced. slice-99 has no Slice Plan row. observed bogus verdict="
        f"{bogus_report.get('verdict')!r}, code={bogus_code}"
    )
    # And it must NOT be byte-identical to the real slice's cleared verdict --
    # the exact false-positive the bug produces (the two are indistinguishable
    # today). A real slice clears; a bogus one must not -> verdicts differ.
    assert not (
        real_report.get("verdict") == "cleared"
        and bogus_report.get("verdict") == "cleared"
    ), (
        "a bogus, never-planned slice must NEVER clear identically to a real "
        "planned slice -- that indistinguishability IS the bug. observed real "
        f"verdict={real_report.get('verdict')!r} (code={real_code}), bogus "
        f"verdict={bogus_report.get('verdict')!r} (code={bogus_code})"
    )
    bogus_slice_plan = _invariant(bogus_report, _INV_SLICE_PLAN)
    assert bogus_slice_plan["satisfied"] is not True, (
        "the slice_plan_section invariant must NOT report satisfied: true for "
        f"a slice with no Slice Plan row. observed={bogus_slice_plan}"
    )
