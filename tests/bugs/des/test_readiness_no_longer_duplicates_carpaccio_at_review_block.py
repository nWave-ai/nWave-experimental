"""Regression -- the readiness gate must stop asking the SAME question
carpaccio already asks, and answering it DIFFERENTLY.

RCA (grounded, orchestrator-confirmed empirically -- do not re-derive):
`src/des/cli/verify_readiness_pre_dispatch.py` owns an invariant id
``_INV_AT_VERDICT = "at_review_verdict"`` whose check `_check_at_review_verdict`
asks EXACTLY the question `src/des/cli/carpaccio_slice_gate.py` assertion 5
(``_AT_REVIEW_REJECTED_EXIT = 45``) asks: does an ``ATReviewVerdict APPROVED``
record exist for the entering slice.

The readiness copy is ADVISORY and RIGOR-GATED: when the record is ABSENT and
``rigor.human_authorization`` is off (the DEFAULT), it returns
``_InvariantResult(satisfied=True, attested=False)`` -- a green light. The
carpaccio copy, running a few nodes later in the SAME ``dispatch.pre`` stack,
is a REAL fail-closed BLOCK (exit 45) that NO rigor flag can disarm. This
violates GDP-7 (a fixed floor, never rigor-gated) and produces two
contradictory answers to one question in one run.

THE FIX (a crafter's job, NOT implemented here -- test-authoring only, zero
`src/` edits): DELETE the readiness invariant entirely -- not make it
always-true. This file pins the OBSERVABLE CONTRACT the fix must satisfy, at
the real CLI edge, so an always-true stub cannot masquerade as the fix:

  1. POSITIVE-after-fix: given a slice with NO ``ATReviewVerdict`` recorded and
     ``rigor.human_authorization`` OFF, the readiness report contains NO
     invariant whose id is ``at_review_verdict`` -- asserted on the ABSENCE of
     the id, so an always-true stub still FAILS this test.
  2. NEGATIVE (the cure must not become the disease): the SAME seeded state
     must STILL be refused by carpaccio assertion 5 with exit 45 -- the
     blocking voice survives the removal.
  3. NEGATIVE: no rigor flag (ON or OFF) changes the carpaccio refusal -- the
     surviving control is not rigor-gated.
  4. NEGATIVE: the readiness gate must not go silently permissive overall --
     its other invariants still evaluate, and it still rejects a genuinely
     unready slice (no feature-delta at all).

RED today (test 1 FAILS for the diagnosed reason): the id IS present in the
emitted report, reported ``satisfied=True`` / ``attested=False``. An
ImportError or collection error would NOT be acceptable RED -- this file
imports nothing from the invariant's own constants (``_INV_AT_VERDICT`` etc.)
so it keeps working, unedited, once the crafter deletes them.

Driving surface (Mandate 13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_readiness_pre_dispatch.main`` and
``des.cli.carpaccio_slice_gate.main`` CLI EDGES, driven in-process via
``tests.common.in_process_cli.run_cli_in_process`` -- mirrors the idiom in
``test_at_review_verdict_refuses_meaningless_identity.py``.

AFFECTED EXISTING TESTS (named for the crafter, NOT edited here -- the fix
will need to update/retire these, they depend on the invariant's presence):
  * tests/bugs/des/test_at_review_guidance_matches_the_real_cli.py
    -- imports ``_INV_AT_VERDICT`` and ``_REMEDIATIONS`` directly (ImportError
    once the constant is deleted).
  * tests/des/unit/cli/test_verify_readiness_pre_dispatch_human_authorization.py
    -- calls ``_check_at_review_verdict`` directly (AttributeError/ImportError
    once the function is deleted).
  * tests/des/unit/cli/test_verify_readiness_pre_dispatch_bugfix_lane.py
    -- ``test_no_lane_runs_all_eight`` asserts the default path's invariant-id
    set is a superset of ``_SKIPPED_SIX | _KEPT_TWO``, which names
    ``"at_review_verdict"`` -- will fail once the id is gone from the default
    8-invariant (now 7) path.
  * tests/des/acceptance/readiness_reuse_invariant/readiness_reuse_invariant_steps/
    domain_types.py + steps_slice_01_walking_skeleton.py -- ``FirstDispatchInvariantId
    .AT_REVIEW_VERDICT`` is a member of ``PRE_EXISTING_INVARIANTS``, asserted
    (via ``then_five_pre_existing_unchanged``) to be reported ``SATISFIED`` --
    will fail once the id no longer appears in the report at all.
  * tests/des/acceptance/readiness_sustainability_invariant/
    readiness_sustainability_invariant_steps/domain_types.py -- declares the
    same ``AT_REVIEW_VERDICT = "at_review_verdict"`` enum member; grep found no
    live assertion consuming it in that directory (likely inert, but worth the
    crafter's eyes).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.carpaccio_slice_gate import main as carpaccio_main
from des.cli.verify_readiness_pre_dispatch import main as readiness_main
from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "fix-readiness-carpaccio-disagree-regression"
_SLICE_ID = "slice-01"
_AT_VERDICT_INVARIANT_ID = "at_review_verdict"
_AT_REVIEW_REJECTED_EXIT = 45


# ---------------------------------------------------------------------------
# Fixture staging -- mirrors `test_at_review_verdict_refuses_meaningless_
# identity.py`'s `_stage_real_feature` idiom: a real Slice Plan row, a real
# tagged .feature scenario, PLUS the Reuse Analysis / Sustainability
# exemption markers so the OTHER 6 (post-fix: 6) readiness invariants clear
# too -- isolating the at_review_verdict invariant as the only thing this
# file is testing, never a false refusal from an unrelated leg.
# ---------------------------------------------------------------------------


def _write_feature_delta(feature_delta_path: Path) -> None:
    feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
    feature_delta_path.write_text(
        "# Feature Delta: readiness/carpaccio at-review disagreement regression\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {_SLICE_ID} | customer sees confirmation | done | | |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: methodology-exempt\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n",
        encoding="utf-8",
    )


def _write_feature_scenario(feature_file_path: Path, feature_id: str) -> None:
    feature_file_path.parent.mkdir(parents=True, exist_ok=True)
    feature_file_path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: Customer checkout\n\n"
        "  @slice-01 @walking_skeleton @driving_port\n"
        "  Scenario: Customer completes checkout and sees confirmation\n"
        "    Given customer has a valid payment method on file\n"
        "    When customer completes checkout\n"
        "    Then customer sees order confirmation\n",
        encoding="utf-8",
    )


def _stage_real_feature(repo: Path, feature_id: str = _FEATURE_ID) -> None:
    """A real, otherwise-clearing feature-delta + tagged scenario, with NO
    ``ATReviewVerdict`` recorded and NO rigor config written (default OFF).

    The ``.git`` marker satisfies ``gate_output_produceable`` too, so every
    OTHER readiness invariant clears and ``at_review_verdict`` (pre-fix) /
    its absence (post-fix) is the ONLY thing that can move the verdict.
    """
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    _write_feature_delta(repo / "docs" / "feature" / feature_id / "feature-delta.md")
    _write_feature_scenario(
        repo / "tests" / "acceptance" / feature_id / "slice-01.feature", feature_id
    )


def _write_rigor_config(repo: Path, human_authorization: bool) -> None:
    nwave = repo / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    (nwave / "des-config.json").write_text(
        json.dumps({"rigor": {"human_authorization": human_authorization}}),
        encoding="utf-8",
    )


def _run_readiness(repo: Path, *extra: str) -> tuple[int, dict[str, object]]:
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _SLICE_ID,
            "--repo-root",
            str(repo),
            *extra,
        ],
        cwd=repo,
        main=readiness_main,
    )
    return exit_code, _parse_last_json_line(stdout, stderr)


def _run_carpaccio(repo: Path, *extra: str) -> tuple[int, dict[str, object]]:
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _SLICE_ID,
            "--repo-root",
            str(repo),
            "--at-kind",
            "gherkin",
            *extra,
        ],
        cwd=repo,
        main=carpaccio_main,
    )
    return exit_code, _parse_last_json_line(stdout, stderr)


def _parse_last_json_line(stdout: str, stderr: str) -> dict[str, object]:
    """The gates emit one JSON line on stdout (carpaccio also co-emits on
    stderr) -- take the LAST well-formed JSON object across both channels, so
    a leading/trailing human-readable line never breaks the parse.
    """
    for chunk in (stdout, stderr):
        for line in reversed(chunk.splitlines()):
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue
    return {}


def _invariant_ids(report: dict[str, object]) -> set[str]:
    return {inv["id"] for inv in report.get("invariants", [])}  # type: ignore[union-attr]


# ===========================================================================
# 1. POSITIVE-after-fix -- RED TODAY: the readiness report must NEVER carry
#    an ``at_review_verdict`` invariant at all (deleted, not stubbed true).
# ===========================================================================


def test_readiness_report_never_carries_the_at_review_verdict_invariant_id(
    tmp_path: Path,
) -> None:
    """No ``ATReviewVerdict`` recorded, default (OFF) rigor -- the readiness
    report must contain NO invariant whose id is ``at_review_verdict``.

    RED today (RCA confirmed): the id IS present, reported
    ``satisfied=True`` / ``attested=False`` -- an advisory green light that
    duplicates (and contradicts) carpaccio's real block. Asserting on the
    ABSENCE of the id -- not on its value -- means an "always satisfied" stub
    still fails this test; only DELETING the invariant passes it.
    """
    repo = tmp_path / "repo"
    _stage_real_feature(repo)

    _exit_code, report = _run_readiness(repo)

    ids = _invariant_ids(report)
    assert _AT_VERDICT_INVARIANT_ID not in ids, (
        "the readiness gate must no longer own an at_review_verdict invariant "
        "at all -- carpaccio's assertion 5 is the one surviving voice on this "
        f"question. observed invariant ids={sorted(ids)}, report={report!r}"
    )


def test_readiness_report_still_evaluates_the_other_feature_readiness_invariants(
    tmp_path: Path,
) -> None:
    """Removing ``at_review_verdict`` must not hollow out the rest of the
    aggregate -- the other feature-readiness invariants still run and are
    reported, over the SAME otherwise-clearing fixture.

    Guards against a lazy "fix" that deletes the WHOLE invariant loop instead
    of the ONE offending invariant.
    """
    repo = tmp_path / "repo"
    _stage_real_feature(repo)

    _exit_code, report = _run_readiness(repo)

    ids = _invariant_ids(report)
    expected_survivors = {
        "slice_plan_section",
        "scenario_slice_tags",
        "gate_output_produceable",
        "pre_commit_scope",
        "reuse_first_or_design_skip",
        "prefactoring_assessment",
        "sustainability",
    }
    assert expected_survivors <= ids, (
        "the other feature-readiness invariants must still be evaluated and "
        f"reported after at_review_verdict is removed. observed ids={sorted(ids)}, "
        f"missing={sorted(expected_survivors - ids)}"
    )


# ===========================================================================
# 2. NEGATIVE -- the cure must not become the disease: carpaccio's REAL block
#    must survive the readiness-side removal, over the IDENTICAL seeded state.
# ===========================================================================


def test_carpaccio_still_refuses_the_identical_seeded_state_with_exit_45(
    tmp_path: Path,
) -> None:
    """The SAME workspace that readiness now advises-clear on
    ``at_review_verdict`` must STILL be hard-refused by carpaccio assertion 5
    (exit 45, ``ATReviewGateRejected``) -- proving the blocking voice is not
    lost, only de-duplicated.

    GREEN today and must STAY green after the fix -- carpaccio's own control
    flow never consulted the readiness invariant, so this is unaffected by
    the deletion; pinned here as the couple's other half.
    """
    repo = tmp_path / "repo"
    _stage_real_feature(repo)

    exit_code, report = _run_carpaccio(repo)

    assert exit_code == _AT_REVIEW_REJECTED_EXIT, (
        "carpaccio assertion 5 must still hard-refuse a slice with no recorded "
        f"ATReviewVerdict -- got exit_code={exit_code}, report={report!r}"
    )
    assert report.get("event") == "ATReviewGateRejected", report
    assert report.get("reason") == "absent", report


# ===========================================================================
# 3. NEGATIVE -- no rigor flag (ON or OFF) may change carpaccio's refusal:
#    the surviving control is not rigor-gated (GDP-7, a fixed floor).
# ===========================================================================


@pytest.mark.parametrize(
    "human_authorization", [False, True], ids=["rigor-off", "rigor-on"]
)
def test_carpaccio_refusal_is_not_rigor_gated(
    tmp_path: Path, human_authorization: bool
) -> None:
    """Neither value of ``rigor.human_authorization`` disarms carpaccio's
    assertion 5 -- unlike the (now-deleted) readiness copy, the surviving
    control is a fixed floor. Carpaccio never reads the rigor axis at all;
    this pins that fact as an observable, not an implementation detail.
    """
    repo = tmp_path / "repo"
    _stage_real_feature(repo)
    _write_rigor_config(repo, human_authorization=human_authorization)

    exit_code, report = _run_carpaccio(repo)

    assert exit_code == _AT_REVIEW_REJECTED_EXIT, (
        f"carpaccio must refuse regardless of rigor.human_authorization="
        f"{human_authorization!r} -- got exit_code={exit_code}, report={report!r}"
    )


# ===========================================================================
# 4. NEGATIVE -- the readiness gate must not go silently permissive overall:
#    it still rejects a genuinely unready slice (no feature-delta at all).
# ===========================================================================


def test_readiness_still_rejects_a_genuinely_unready_slice(tmp_path: Path) -> None:
    """A slice with NO feature-delta.md at all (no Slice Plan section) must
    still be REFUSED by the readiness gate -- proving the deletion of
    ``at_review_verdict`` did not turn the aggregate into a rubber stamp.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").mkdir()  # satisfies gate_output_produceable only

    exit_code, report = _run_readiness(repo)

    assert exit_code != 0, (
        "a slice with no feature-delta at all must be REFUSED, not cleared -- "
        f"got exit_code={exit_code}, report={report!r}"
    )
    assert report.get("verdict") == "refused", report
    slice_plan_results = [
        inv
        for inv in report.get("invariants", [])  # type: ignore[union-attr]
        if inv["id"] == "slice_plan_section"
    ]
    assert slice_plan_results and slice_plan_results[0]["satisfied"] is False, (
        "the slice_plan_section invariant must still fire (and fail) for a "
        f"feature with no feature-delta.md -- observed invariants="
        f"{report.get('invariants')!r}"
    )
