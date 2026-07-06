"""RC4-b: a declared bugfix lane skips the heavy feature-readiness ceremony.

Root cause (docs/feedback/des-spine-ceremony-cost-attack-plan.md, RC4 fix-ask #1):
the readiness gate `verify_readiness_pre_dispatch` enforces the SAME 7 feature-readiness
invariants for EVERY atdd_pure DELIVER dispatch — a 10-line bugfix pays the full
slice-plan + scenario-tags + AT-review + reuse-first + sustainability ceremony, which
is disproportionate (Ale 2026-06-26: "valore quando serve un processo rigoroso, niente
cerimonie inutili").

Cure (RC4-b, lane-keyed, ADD-not-mutate; skip-set + anti-abuse corroborated cross-tier
by Tsunami Q-10): a dispatch may declare a `DES-LANE: bugfix` lane. When declared WITH
a non-vacuous justification that NAMES the defect + the regression-test, the gate SKIPS
the 5 feature-readiness invariants `{slice_plan_section, scenario_slice_tags,
at_review_verdict, reuse_first_or_design_skip, sustainability}` and enforces ONLY the 2
mechanical safety guards `{gate_output_produceable, pre_commit_scope}` — and emits a
LOUD, durable `lane` audit record naming the skip + the justification.

ANTI-ABUSE (fail-closed, the safety mechanism for the one skipped quality gate
`at_review_verdict`): a `DES-LANE: bugfix` with an EMPTY or VACUOUS justification (one
that does NOT name a regression-test) is REFUSED — the lane cannot become the shortcut
to skip AT review on a real feature mislabeled as a bugfix. Default (no lane marker) =
all 7 enforced, byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.cli import verify_readiness_pre_dispatch as gate


_FEATURE_ID = "synthetic-bugfix-lane-feature"
_SLICE_ID = "slice-01"

# The 5 feature-readiness invariants the bugfix lane skips, and the 2 it keeps.
_SKIPPED_FIVE = frozenset(
    {
        "slice_plan_section",
        "scenario_slice_tags",
        "at_review_verdict",
        "reuse_first_or_design_skip",
        "sustainability",
    }
)
_KEPT_TWO = frozenset({"gate_output_produceable", "pre_commit_scope"})

# A valid lane justification NAMES the defect + the regression-test (Tsunami's
# anti-abuse refinement) — the gate grants the skip only for this shape.
_VALID_JUSTIFICATION = (
    "off-by-one in _resolve_head_sha returns the parent commit; "
    "regression test test_resolve_head_sha_returns_head pins it RED->GREEN"
)
# A vacuous justification names neither a defect nor a regression-test -> refused.
_VACUOUS_JUSTIFICATION = "just fixing a thing"


def _run(repo: Path, *extra: str):
    """Invoke the gate main with the base args + capture the emitted JSON report."""
    import contextlib
    import io

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


def test_no_lane_runs_all_seven(tmp_path: Path) -> None:
    """Regression-lock: no DES-LANE marker → all 7 invariants enforced (byte-stable)."""
    _, report = _run(tmp_path)
    ids = _invariant_ids(report)
    assert ids >= _SKIPPED_FIVE | _KEPT_TWO, (
        "the default path (no lane) must enforce all 7 feature-readiness invariants "
        f"byte-identically. observed invariant ids={sorted(ids)}"
    )


def test_bugfix_lane_skips_the_five_feature_readiness(tmp_path: Path) -> None:
    """A bugfix lane with a valid justification runs ONLY the 2 mechanical guards."""
    _, report = _run(
        tmp_path, "--lane", "bugfix", "--lane-justification", _VALID_JUSTIFICATION
    )
    ids = _invariant_ids(report)
    assert ids == set(_KEPT_TWO), (
        "a DES-LANE: bugfix dispatch with a valid (defect + regression-test) "
        "justification must SKIP the 5 feature-readiness invariants and run ONLY the 2 "
        f"mechanical guards {sorted(_KEPT_TWO)}. observed={sorted(ids)}"
    )


def test_bugfix_lane_emits_loud_audit_record(tmp_path: Path) -> None:
    """The lane skip is LOUD + durable: a `lane` record names the skip + justification."""
    _, report = _run(
        tmp_path, "--lane", "bugfix", "--lane-justification", _VALID_JUSTIFICATION
    )
    lane = report.get("lane")
    assert isinstance(lane, dict), (
        "the bugfix-lane skip must emit a LOUD audit record (`lane` object) — the "
        "anti-abuse logging is the safety mechanism for the skipped AT review. "
        f"observed report keys={sorted(report)}"
    )
    assert lane.get("lane") == "bugfix"
    assert _VALID_JUSTIFICATION in (lane.get("justification") or "")
    assert set(lane.get("skipped") or []) == set(_SKIPPED_FIVE), (
        "the lane record must NAME the skipped invariants for the audit trail. "
        f"observed skipped={lane.get('skipped')}"
    )


def test_bugfix_lane_empty_justification_refused(tmp_path: Path) -> None:
    """Anti-abuse: an EMPTY justification fails closed — the lane is refused."""
    code, report = _run(tmp_path, "--lane", "bugfix", "--lane-justification", "")
    assert code != 0 and report.get("verdict") == "refused", (
        "a DES-LANE: bugfix with an EMPTY justification must FAIL CLOSED (refused) — "
        "the lane cannot skip AT review without naming the defect + regression-test. "
        f"observed code={code}, verdict={report.get('verdict')}"
    )


def test_bugfix_lane_vacuous_justification_refused(tmp_path: Path) -> None:
    """Anti-abuse: a justification that names no regression-test is refused (strict)."""
    code, report = _run(
        tmp_path, "--lane", "bugfix", "--lane-justification", _VACUOUS_JUSTIFICATION
    )
    assert code != 0 and report.get("verdict") == "refused", (
        "a DES-LANE: bugfix whose justification does NOT name a regression-test must "
        "FAIL CLOSED (refused) — Tsunami Q-10 anti-abuse: the strict justification is "
        "the safety mechanism for the one skipped quality gate (at_review_verdict). "
        f"observed code={code}, verdict={report.get('verdict')}"
    )


def test_bugfix_lane_zero_red_evidence_and_no_expectation_refused(
    tmp_path: Path,
) -> None:
    """Regression (nw-user-examiner Vera, verdict FAIL, seal 6d182a2a, NEGATIVE-2):
    a bugfix lane with a VALID (anti-abuse-passing) justification but ZERO
    RED->GREEN mechanical-seal evidence (no `.nwave/telemetry/red-green/*.json`
    seal — see `des verify-red-green --record-red`) and NO expectation charter
    authored under `docs/product/expectations/` must be REFUSED.

    Charter (the oracle): `docs/product/expectations/
    v2-readiness-gate-lightweight-for-small-slices/
    a-tiny-bugfix-slice-closes-without-heavy-feature-delta-ceremony.md`,
    NEGATIVE: "the mechanical seal is still required — a slice with NO RED
    evidence and NO expectation still CANNOT close (we lighten ceremony, we do
    not remove the evidence floor)."

    Today the bugfix lane only re-checks the 2 mechanical guards
    (`gate_output_produceable`, `pre_commit_scope`) and never looks at the
    RED->GREEN seal or the expectation charter at all -- so this dispatch
    wrongly CLEARS. The `.git` marker below satisfies `gate_output_produceable`
    by construction (and no `tests/` dir exists, vacuously satisfying
    `pre_commit_scope`), isolating the missing evidence-floor check as the sole
    cause of the wrong `cleared` verdict.
    """
    (tmp_path / ".git").mkdir()
    # No docs/product/expectations/** authored, no .nwave/telemetry/red-green/
    # seal recorded -- zero RED->GREEN mechanical-seal evidence, zero expectation.
    code, report = _run(
        tmp_path, "--lane", "bugfix", "--lane-justification", _VALID_JUSTIFICATION
    )
    assert report.get("verdict") == "refused" and code != 0, (
        "a DES-LANE: bugfix dispatch with NO RED->GREEN seal and NO expectation "
        "charter must be REFUSED — the evidence floor holds even when the heavy "
        "feature-readiness ceremony is lightened. "
        f"observed verdict={report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )
    assert any(
        not inv["satisfied"] and inv.get("remediation")
        for inv in report.get("invariants", [])
    ), (
        "the refusal must carry a diagnostic naming the missing evidence floor "
        f"(what/why/how). observed invariants={report.get('invariants')}"
    )
