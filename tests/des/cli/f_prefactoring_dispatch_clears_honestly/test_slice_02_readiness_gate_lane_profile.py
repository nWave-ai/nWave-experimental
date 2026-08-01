"""slice-02 ATs -- the readiness gate consults LANE_PROFILES, never branches.

# @feature-f-prefactoring-dispatch-clears-honestly
# @slice-02

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`, row 1 keystone). Design reference:
`docs/feature/f-prefactoring-dispatch-clears-honestly/feature-delta.md`
(`## Wave: DESIGN / [REF] Per-Locus Consulting Mechanism`, slice-02 code
block) + the "DELIVER reconciliation (2026-07-05)" note: Tsunami
`reads_of LANE_PROFILES` confirms slice-01 (`atdd_pure_prompt_validator.py`)
and slice-03 (`carpaccio_format.py`) already consult the datum;
`verify_readiness_pre_dispatch.py` is the ONE remaining consulting locus that
does NOT -- `main()` only branches on ``lane == _BUGFIX_LANE``, with no
``elif lane_name in LANE_PROFILES`` at all. This file drives that gap.

Reuse anchor (mirrored, not duplicated): the SAME `DES-LANE: bugfix` shape
precedent (`tests/des/unit/cli/test_verify_readiness_pre_dispatch_bugfix_lane.py`)
-- same `gate.main(argv)` driving port, same stdout-JSON capture helper, same
`_invariant_ids` oracle shape. The "no lane at all -> full 7 invariants"
regression-lock is ALREADY covered there (`test_no_lane_runs_all_seven`) and is
NOT duplicated here (Mandate 12 consolidation).

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
`des.cli.verify_readiness_pre_dispatch.main(argv)` -- the SAME composition
root `des verify-readiness-pre-dispatch` dispatches -- never a bare
`LaneProfile`/`LANE_PROFILES` shape assertion with no port between.

Active-RED contract: `main()` today ignores any `--lane` value other than
`"bugfix"` and silently falls through to the full 7-invariant default path --
every scenario below that depends on a `prefactoring` lane being recognized
fails with a semantic `AssertionError` (the datum is never consulted), never
an import/collection error.
"""

from __future__ import annotations

import contextlib
import io
import json
from typing import TYPE_CHECKING

from des.cli import verify_readiness_pre_dispatch as gate
from des.domain.expectation_charter_mapping import CharterObligation
from des.domain.lane_profile import LANE_PROFILES, AtRequirement, GuardKind, LaneProfile


if TYPE_CHECKING:
    from pathlib import Path


_FEATURE_ID = "synthetic-prefactoring-lane-feature"
_SLICE_ID = "slice-02"


def _run(repo: Path, *extra: str):
    """Invoke the gate main with the base args + capture the emitted JSON report.

    Mirrors `test_verify_readiness_pre_dispatch_bugfix_lane.py`'s own `_run`
    helper verbatim -- same driving surface, same stdout-JSON capture shape.
    """
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--slice-id",
        _SLICE_ID,
        "--repo-root",
        str(repo),
        *extra,
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


def _invariant_ids(report: dict) -> set[str]:
    return {inv["id"] for inv in report.get("invariants", [])}


# AT-1 (positive -- skip-set read from the datum, admitted) -------------------


def test_prefactoring_lane_skips_datum_named_invariants_and_clears(
    tmp_path: Path,
) -> None:
    """A `DES-LANE: prefactoring` dispatch skips exactly the invariants named
    in `LANE_PROFILES["prefactoring"].skipped_invariants` -- computed from the
    LIVE datum, never a hardcoded literal in this test -- and clears (verdict
    "cleared", exit 0) once the 2 kept mechanical guards are satisfied
    (`.git` present, no `tests/` dir -> both vacuously/actually satisfied).

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: feature-delta.md (Wave: DESIGN / [REF] Per-Locus
    Consulting Mechanism, slice-02 code block).
    """
    (tmp_path / ".git").mkdir()
    profile = LANE_PROFILES["prefactoring"]
    expected_kept = set(gate._ALL_INVARIANTS) - set(profile.skipped_invariants)

    code, report = _run(tmp_path, "--lane", "prefactoring")

    ids = _invariant_ids(report)
    assert ids == expected_kept, (
        "a DES-LANE: prefactoring dispatch must run ONLY the invariants NOT "
        f"named in LANE_PROFILES['prefactoring'].skipped_invariants "
        f"(expected={sorted(expected_kept)}). observed={sorted(ids)} -- the "
        "readiness gate does not yet consult LANE_PROFILES for this lane."
    )
    assert report.get("verdict") == "cleared" and code == 0, (
        "a prefactoring dispatch with both kept mechanical guards satisfied "
        f"must clear (verdict='cleared', exit 0). observed verdict="
        f"{report.get('verdict')!r}, code={code}, invariants={report.get('invariants')}"
    )


# AT-2 (positive -- LOUD audit record names skip-set + guard-kind) ------------


def test_prefactoring_lane_audit_record_names_skip_set_and_guard_kind(
    tmp_path: Path,
) -> None:
    """The lane skip is LOUD + durable: a `lane` record names the lane id,
    the skipped invariants, AND the guard-kind the datum declares
    (`GREEN_TO_GREEN` for prefactoring -- the mirror of how a `bugfix` lane's
    record is keyed to `RED_TO_GREEN` admission). Every expected value is
    read from the LIVE `LANE_PROFILES["prefactoring"]` entry, never a literal
    duplicated in this test.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: feature-delta.md (Wave: DESIGN / [REF] Per-Locus
    Consulting Mechanism, slice-02 code block; LOUD audit-record mandate).
    """
    (tmp_path / ".git").mkdir()
    profile = LANE_PROFILES["prefactoring"]

    _, report = _run(tmp_path, "--lane", "prefactoring")

    lane = report.get("lane")
    assert isinstance(lane, dict), (
        "a DES-LANE: prefactoring dispatch must emit a LOUD audit record "
        "(`lane` object) naming the lane + what it skipped -- mirroring the "
        f"bugfix lane's own audit record. observed report keys={sorted(report)}"
    )
    assert lane.get("lane") == "prefactoring"
    assert set(lane.get("skipped") or []) == set(profile.skipped_invariants), (
        "the lane record must NAME the skipped invariants for the audit "
        f"trail, read from the datum. observed skipped={lane.get('skipped')}, "
        f"datum skipped_invariants={profile.skipped_invariants}"
    )
    # CONTRACT_SHAPE: bounded-change
    # Outcome anchor: feature-delta.md (Wave: DESIGN / [REF] Per-Locus
    # Consulting Mechanism, slice-02 code block; LOUD audit-record mandate).
    assert lane.get("guard_kind") == profile.guard_kind.value, (
        "the lane record must NAME the guard-kind the datum declares "
        f"(GREEN_TO_GREEN for prefactoring) -- observed guard_kind="
        f"{lane.get('guard_kind')!r}, datum guard_kind={profile.guard_kind.value!r}"
    )


# AT-3 (litmus -- datum consulted live, not a hardcoded branch) ---------------


def test_prefactoring_lane_consults_datum_live_not_hardcoded(
    tmp_path: Path, monkeypatch
) -> None:
    """Structural claim: the readiness gate LOOKS UP `LANE_PROFILES` at call
    time -- it does not hardcode "prefactoring"'s skip-set or guard-kind.
    Proven by substituting the datum entry the gate consults (narrowing the
    skip-set from 5 invariants to 1, and swapping `guard_kind` from
    `GREEN_TO_GREEN` to `RED_TO_GREEN`) and observing the decision follow the
    SUBSTITUTED shape, not a baked-in one -- the litmus this feature's DESIGN
    names: if `LANE_PROFILES["prefactoring"]` changed its skip-set, the
    gate's behavior must change.

    `raising=False`: pre-GREEN, `des.cli.verify_readiness_pre_dispatch` does
    not import `LANE_PROFILES` at all yet -- the monkeypatch is a no-op then,
    which is the correct RED (nothing to consult -> falls through to the full
    7-invariant default, contradicting this test's 6-invariant expectation).
    """
    (tmp_path / ".git").mkdir()
    substituted_profiles = {
        "prefactoring": LaneProfile(
            lane_id="prefactoring",
            required_sections=(),
            guard_kind=GuardKind.RED_TO_GREEN,
            feature_readiness=False,
            at_requirement=AtRequirement.EXEMPT,
            skipped_invariants=("slice_plan_section",),
            annotation_token="prefactoring",
            charter_obligation=CharterObligation.EXEMPT,
        )
    }
    monkeypatch.setattr(gate, "LANE_PROFILES", substituted_profiles, raising=False)

    _, report = _run(tmp_path, "--lane", "prefactoring")

    expected_kept = set(gate._ALL_INVARIANTS) - {"slice_plan_section"}
    ids = _invariant_ids(report)
    assert ids == expected_kept, (
        "the gate must read the skip-set from `LANE_PROFILES` at call time "
        "-- with the datum entry substituted to skip ONLY "
        "'slice_plan_section', a prefactoring dispatch must run the other 6 "
        "invariants. A hardcoded 'prefactoring' branch (ignoring the "
        f"substitution) would still skip the real 5. observed={sorted(ids)}, "
        f"expected={sorted(expected_kept)}"
    )
    lane = report.get("lane") or {}
    assert lane.get("guard_kind") == "RED_TO_GREEN", (
        "the gate must read `guard_kind` from the datum at call time -- with "
        "the substituted entry declaring RED_TO_GREEN, the audit record must "
        f"reflect it, not the datum's real GREEN_TO_GREEN default. observed="
        f"{lane.get('guard_kind')!r}"
    )


# AT-4 (negative/leak-guard -- exemption does not leak to unrecognized lanes) -


def test_unknown_lane_keeps_full_ceremony_while_prefactoring_lane_exempts(
    tmp_path: Path,
) -> None:
    """KPI-2 guardrail: an unrecognized `--lane` value (neither `bugfix` nor a
    `LANE_PROFILES` key) still runs the FULL 7 invariants, byte-identical to
    today -- the prefactoring exemption must not leak into an ordinary
    dispatch that merely mistypes/guesses a lane name. Contrasted, in the
    SAME test, against the real `prefactoring` lane on the identical repo
    fixture -- which DOES exempt the datum-named invariants -- so the
    negative claim is proven meaningful, not vacuously true.
    """
    (tmp_path / ".git").mkdir()

    _, unknown_report = _run(tmp_path, "--lane", "unknown-lane-xyz")
    assert _invariant_ids(unknown_report) == set(gate._ALL_INVARIANTS), (
        "an unrecognized --lane value must NOT exempt any invariant -- all 7 "
        f"must still run. observed={sorted(_invariant_ids(unknown_report))}"
    )
    assert unknown_report.get("lane") is None, (
        "an unrecognized --lane value must emit NO lane audit record. "
        f"observed={unknown_report.get('lane')!r}"
    )

    profile = LANE_PROFILES["prefactoring"]
    expected_kept = set(gate._ALL_INVARIANTS) - set(profile.skipped_invariants)
    _, prefactoring_report = _run(tmp_path, "--lane", "prefactoring")
    assert _invariant_ids(prefactoring_report) == expected_kept, (
        "on the SAME repo fixture, a recognized DES-LANE: prefactoring value "
        "must exempt the datum-named invariants -- contrasting the "
        "unrecognized-lane case above. observed="
        f"{sorted(_invariant_ids(prefactoring_report))}, expected="
        f"{sorted(expected_kept)} -- the readiness gate does not yet consult "
        "LANE_PROFILES for this lane."
    )
    assert (prefactoring_report.get("lane") or {}).get("lane") == "prefactoring", (
        "the recognized prefactoring lane must emit its own audit record "
        f"naming the lane. observed={prefactoring_report.get('lane')!r}"
    )
