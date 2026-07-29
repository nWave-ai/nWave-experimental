# @feature-declared-facts-reachable-recorded
# @slice-01
"""F3 (AT-review rejections leave a ledger trace) -- ``record_review_outcome``
(``src/des/cli/at_review_verdict.py:137-188``) currently short-circuits
``if verdict != _APPROVED: return False``, writing NOTHING to the AT-completion
ledger for a ``NEEDS_REVISION`` verdict. Consequence measured on the real
ledger (feature-delta Theme): review verdicts read as 100% APPROVED, because a
rejection leaves no trace at all -- the ledger cannot distinguish "reviewed and
rejected" from "never reviewed".

Design authority: ``docs/feature/declared-facts-reachable-recorded/
feature-delta.md`` DD-1 (both-outcomes write) + DD-2 (a robustness-density-gate
block on an otherwise-APPROVED call is recorded as ``NEEDS_REVISION`` +
``blocked_by="robustness-density-gate"``, never silence).

Driving surface (Mandate 13, driving-port-only): the REAL
``des.cli.at_review_verdict.main(argv)`` CLI EDGE, driven in-process via
``tests.common.in_process_cli.run_cli_in_process`` (the in-process analogue of
the ``des record-at-review-verdict ...`` dispatcher invocation) under an
isolated ``tmp_path`` repo -- never the real ``.nwave/telemetry/``.

RED-for-right-reason: every positive assertion below fails today with a
genuine semantic ``AssertionError`` (a ledger record that should exist is
absent, or an exit code that should be non-zero is 0) -- never an
import/collection error, confirmed by an interactive probe against this
module before authoring (see the DELIVER-facing report accompanying this
slice for the empirical transcript).

Behavior #4 of the slice brief ("the consumer still refuses a NEEDS_REVISION
record") is DELIBERATELY not tested here: ``carpaccio_slice_gate.
_check_verdict_record`` (``src/des/cli/carpaccio_slice_gate.py:610-611``)
already rejects on ``record.get("verdict") != "APPROVED"`` unconditionally --
it does not care how the record got onto the ledger. Empirically verified
(the reason-code + exit-code below, not the design's reading) by writing a
NEEDS_REVISION record directly onto a fixture ledger and running the real
``carpaccio_slice_gate.main`` against it: exit code 45, reason
``not-approved``. An existing regression test already pins this exact fixture
shape for the CURRENT (pre-DD-1) world --
``tests/scripts/cli/atdd_pure_carpaccio_slice_gate/steps/
test_carpaccio_entry_path_fixes.py::test_f02_at_review_verdict_cli_needs_revision_writes_nothing``
asserts ``gate_exit == 45`` / ``reason == "absent"`` for a NEEDS_REVISION call
that (today) writes no record. That existing test's assertions become
CORRECT-BUT-STALE the moment DD-1 lands (a record will exist, so the gate's
reason moves from "absent" to "not-approved") -- the DELIVER crafter will need
to update it; this DISTILL slice does not touch it (boundary rule: existing
test files are off-limits here).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.at_review_verdict import main as record_at_review_verdict_main
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker


_REPO_ROOT = Path(__file__).resolve().parents[4]
_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"
_SLICE_ID = "slice-01"

_SCENARIO_BODY = (
    "  Given a fixture precondition\n"
    "  When the fixture action occurs\n"
    "  Then the fixture outcome holds\n"
)

# The content-seal ``at_content_hash`` the producer computes for a single
# scenario carrying the body above -- mirrors ``carpaccio_slice_gate.
# _at_content_hash``'s normalization (lowercased Given/When/Then lines,
# joined, sha256). Not asserted on directly here (the producer derives it
# itself); kept only for readers who want to cross-check a fixture ledger by
# hand.
_ONE_SCENARIO_CONTENT_HASH = hashlib.sha256(
    b"given a fixture precondition\n"
    b"when the fixture action occurs\n"
    b"then the fixture outcome holds"
).hexdigest()


# ---------------------------------------------------------------------------
# Fixture builders -- a real feature-delta + a real @slice-01 .feature
# scenario, mirroring the shape ``tests/bugs/des/
# test_record_at_review_verdict_refuses_imaginary_slice.py`` and
# ``tests/scripts/cli/atdd_pure_carpaccio_slice_gate`` already establish for
# this exact CLI.
# ---------------------------------------------------------------------------


def _write_real_feature_delta(repo_root: Path, feature_id: str) -> None:
    feature_delta_path = (
        repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
    feature_delta_path.write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {_SLICE_ID} | fixture slice | pending | | |\n",
        encoding="utf-8",
    )


def _write_real_feature_scenario(repo_root: Path, feature_id: str) -> None:
    feature_file_path = (
        repo_root / "tests" / "domain" / "acceptance" / f"{feature_id}.feature"
    )
    feature_file_path.parent.mkdir(parents=True, exist_ok=True)
    feature_file_path.write_text(
        f"@feature-{feature_id}\n"
        f"Feature: {feature_id} fixture\n\n"
        f"  @{_SLICE_ID}\n"
        "  Scenario: fixture scenario\n"
        f"{_SCENARIO_BODY}",
        encoding="utf-8",
    )


def _base_argv(
    *, feature_id: str, slice_id: str, repo_root: Path, verdict: str
) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        verdict,
        "--reviewer-agent-id",
        _REVIEWER_AGENT_ID,
        "--repo-root",
        str(repo_root),
    ]


def _run_producer(repo_root: Path, argv: list[str]) -> tuple[int, str, str]:
    """Drive the REAL ``des record-at-review-verdict`` CLI EDGE in-process."""
    return run_cli_in_process(argv, cwd=repo_root, main=record_at_review_verdict_main)


def _read_verdict_records(
    repo_root: Path, feature_id: str, slice_id: str
) -> list[dict[str, object]]:
    """Every ``ATReviewVerdict`` ledger record for ``feature_id``/``slice_id``.

    ``AtCompletionLedger.read_records`` already treats an absent ledger file
    as "no records" (empty list), never an error -- no pre-check needed.
    """
    return AtCompletionLedger(feature_id, repo_root).read_records(
        event_type="ATReviewVerdict", slice_id=slice_id
    )


# ===========================================================================
# 1. NEEDS_REVISION leaves a ledger record (+ regression pin for behavior #5:
#    the human/CLI surface must key on the VERDICT, never on "did we write").
# ===========================================================================


def test_needs_revision_verdict_appends_ledger_record_and_surface_never_reports_pass(
    tmp_path: Path,
) -> None:
    """A ``NEEDS_REVISION`` verdict for a REAL feature/slice must append
    exactly one ``ATReviewVerdict`` record whose ``verdict`` field is
    ``"NEEDS_REVISION"`` (DD-1 both-outcomes write).

    Today ``record_review_outcome`` returns ``False`` without ever calling
    ``record_at_review_verdict`` for a non-APPROVED verdict, so the ledger
    stays empty -- the F3 defect this slice closes.

    Regression pin (behavior #5): once the write lands, ``written`` becomes
    ``True`` for a rejection too. The human surface
    (``at_review_verdict.main``'s ``Verdict.PASS if written else
    Verdict.DEGRADED``) must NOT flip to PASS merely because a write
    happened -- it must key on the requested verdict. Asserted via the
    ``human_surface`` module's own unique badge string (``"✅ PASS"``,
    ``des.cli.human_surface._PREFIX_BY_VERDICT[Verdict.PASS]``) never
    appearing on stderr for a NEEDS_REVISION call, and the emitted
    ``ATReviewVerdictCLI`` JSON event's own ``verdict`` field continuing to
    read ``"NEEDS_REVISION"`` (never silently coerced).
    """
    repo = tmp_path / "repo"
    feature_id = "declared-facts-at1-fixture"
    _write_real_feature_delta(repo, feature_id)
    _write_real_feature_scenario(repo, feature_id)

    exit_code, stdout, stderr = _run_producer(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=_SLICE_ID,
            repo_root=repo,
            verdict="NEEDS_REVISION",
        ),
    )

    records = _read_verdict_records(repo, feature_id, _SLICE_ID)
    assert len(records) == 1, (
        "a NEEDS_REVISION verdict for a real feature/slice must append "
        "exactly one ATReviewVerdict ledger record (DD-1 both-outcomes "
        f"write) -- got {records!r} (exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}). Today "
        "`record_review_outcome` short-circuits `if verdict != APPROVED: "
        "return False`, writing nothing for a rejection."
    )
    assert records[0].get("verdict") == "NEEDS_REVISION", records[0]

    assert "✅ PASS" not in stderr, (
        "a NEEDS_REVISION verdict must never be reported on the human "
        f"surface with the PASS badge -- got stderr={stderr!r}. A fix that "
        "makes `written` True for NEEDS_REVISION without also keying the "
        "human_verdict off the requested verdict (not off `written`) would "
        "regress this."
    )
    event_lines = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip().startswith("{") and line.strip().endswith("}")
    ]
    assert event_lines, (
        f"expected an ATReviewVerdictCLI JSON event on stdout, got {stdout!r}"
    )
    import json as _json

    last_event = _json.loads(event_lines[-1])
    assert last_event.get("verdict") == "NEEDS_REVISION", last_event


# ===========================================================================
# 2. Bounded change -- record count appended equals call count, for every
#    verdict value, never zero, never two.
# ===========================================================================


def test_bounded_change_one_ledger_record_appended_per_call_across_verdicts(
    tmp_path: Path,
) -> None:
    """Three sequential calls (NEEDS_REVISION, NEEDS_REVISION, APPROVED) on
    the SAME feature/slice must leave the ledger record count monotonically
    tracking the call count: 1, then 2, then 3.

    Today the sequence is 0, 0, 1 -- every NEEDS_REVISION call is a silent
    no-op (bounded-change contract-shape violated: 0 records appended, not
    exactly 1, per DD-1's own "exactly one ledger record appended per call"
    Contract-Test row).
    """
    repo = tmp_path / "repo"
    feature_id = "declared-facts-at2-fixture"
    _write_real_feature_delta(repo, feature_id)
    _write_real_feature_scenario(repo, feature_id)

    expected_counts_after_each_call = [1, 2, 3]
    verdict_sequence = ["NEEDS_REVISION", "NEEDS_REVISION", "APPROVED"]

    for call_number, (verdict, expected_count) in enumerate(
        zip(verdict_sequence, expected_counts_after_each_call, strict=True), start=1
    ):
        exit_code, stdout, stderr = _run_producer(
            repo,
            _base_argv(
                feature_id=feature_id,
                slice_id=_SLICE_ID,
                repo_root=repo,
                verdict=verdict,
            ),
        )
        records = _read_verdict_records(repo, feature_id, _SLICE_ID)
        assert len(records) == expected_count, (
            f"after call #{call_number} (verdict={verdict!r}) the ledger "
            f"must carry exactly {expected_count} ATReviewVerdict record(s) "
            f"-- got {len(records)} ({records!r}). Bounded-change contract: "
            "each call appends exactly one record, regardless of verdict "
            f"(exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r})."
        )


# ===========================================================================
# 3. DD-2: the robustness-density-gate block is recorded, not silent.
# ===========================================================================


def test_robustness_gate_block_records_needs_revision_with_blocked_by_reason(
    tmp_path: Path,
) -> None:
    """When both robustness flags are supplied and the density gate exits
    non-zero on an otherwise-APPROVED call, a record MUST be written with
    ``verdict="NEEDS_REVISION"`` and ``blocked_by="robustness-density-gate"``
    -- never silence.

    Fixture: a declaration YAML carrying no ``unbounded-input-domains`` block
    while the staged AT scope has an acceptance test present triggers
    ``check_robustness_density``'s ``RobustnessDeclarationMissing`` refusal
    (exit 1) -- confirmed by an interactive probe against the real gate CLI
    before authoring this test (stderr carries the
    ``RobustnessDeclarationMissing`` token).

    Today ``record_review_outcome`` returns ``False`` on a non-zero gate exit
    WITHOUT ever calling ``record_at_review_verdict`` -- the ledger stays
    empty. This is the second (currently silent) half of the F3 defect DD-2
    closes.
    """
    repo = tmp_path / "repo"
    feature_id = "declared-facts-at3-fixture"
    _write_real_feature_delta(repo, feature_id)
    _write_real_feature_scenario(repo, feature_id)

    # The robustness gate CLI (`scripts.cli.check_robustness_density`) is
    # consulted by `record_review_outcome` as a NESTED real subprocess
    # (`cwd=str(repo_root)`, i.e. the tmp fixture). Two environment
    # preconditions make that nested subprocess actually run the gate's own
    # logic instead of dying on an unrelated environment check:
    #   * `seed_dev_checkout_marker` -- an empty `.git/` so the child's own
    #     runtime-freshness probe autoskips instead of fail-closed exit 78
    #     on a manifest-less tmp tree (see `tests/env_parity.py`).
    #   * `PYTHONPATH` including this real repo root -- so `scripts.cli.
    #     check_robustness_density` (a `scripts.*` namespace package, not
    #     `des.*`) is importable regardless of the nested subprocess's cwd.
    # Established precedent: `tests/des/acceptance/fix_robustness_pbt_density_gate/
    # steps/composition.py::when_run_at_review_verdict_producer_with_gate_wired`.
    seed_dev_checkout_marker(repo)

    declaration_path = repo / "unbounded-domains.yaml"
    declaration_path.write_text("{}\n", encoding="utf-8")
    at_scope_dir = repo / "at_scope"
    at_scope_dir.mkdir(parents=True, exist_ok=True)
    (at_scope_dir / "test_dummy.py").write_text(
        "def test_dummy():\n    assert True\n", encoding="utf-8"
    )

    saved_env = dict(os.environ)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        (str(_REPO_ROOT / "src"), str(_REPO_ROOT))
    )
    try:
        argv = _base_argv(
            feature_id=feature_id,
            slice_id=_SLICE_ID,
            repo_root=repo,
            verdict="APPROVED",
        ) + [
            "--robustness-declaration",
            str(declaration_path),
            "--robustness-at-scope",
            str(at_scope_dir),
        ]
        exit_code, stdout, stderr = run_cli_in_process(
            argv, cwd=_REPO_ROOT, main=record_at_review_verdict_main
        )
    finally:
        os.environ.clear()
        os.environ.update(saved_env)

    assert "RobustnessDeclarationMissing" in stderr, (
        "test setup invariant: the staged declaration must trigger the "
        f"robustness gate's own refusal -- got stderr={stderr!r} "
        f"(exit_code={exit_code}, stdout={stdout!r}). If this fails, the "
        "fixture is not exercising a genuine gate block."
    )

    records = _read_verdict_records(repo, feature_id, _SLICE_ID)
    assert len(records) == 1, (
        "a robustness-gate block on an otherwise-APPROVED call must append "
        "a NEEDS_REVISION record (DD-2), never write nothing -- got "
        f"{records!r} (exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}). Today `record_review_outcome` returns False "
        "on a non-zero gate exit without ever calling "
        "`record_at_review_verdict` -- the ledger stays silently empty."
    )
    assert records[0].get("verdict") == "NEEDS_REVISION", records[0]
    assert records[0].get("blocked_by") == "robustness-density-gate", records[0]


# ===========================================================================
# 4. NEGATIVE -- the imaginary-slice guard extends to the newly-writing
#    NEEDS_REVISION path. Today `_verify_feature_slice_exists` runs ONLY
#    under `if args.verdict == _APPROVED`, precisely because NEEDS_REVISION
#    wrote nothing. Once it writes, an unguarded NEEDS_REVISION for a
#    non-existent feature would append a ledger record for a thing that does
#    not exist -- reopening the defect
#    `tests/bugs/des/test_record_at_review_verdict_refuses_imaginary_slice.py`
#    already guards for APPROVED.
# ===========================================================================


@pytest.mark.negative_at
def test_needs_revision_never_writes_a_record_for_an_imaginary_feature_slice(
    tmp_path: Path,
) -> None:
    """A ``NEEDS_REVISION`` verdict for a feature with NO
    ``docs/feature/{feature_id}/feature-delta.md`` (an imaginary feature/slice)
    must be REFUSED (non-zero exit) and must NEVER append a ledger record --
    even though a real, correctly-tagged ``.feature`` scenario exists (so AT
    derivation itself would otherwise succeed).

    Today: `main()` only calls `_verify_feature_slice_exists` when
    `args.verdict == "APPROVED"`. A NEEDS_REVISION call for this exact
    imaginary feature/slice runs to completion, exits 0, and writes nothing
    (verdict != APPROVED short-circuits `record_review_outcome` regardless of
    existence) -- so today it happens to be silent-safe BY ACCIDENT of the F3
    defect, not by any refusal. Confirmed empirically before authoring: today
    `exit_code == 0`. Once DD-1 makes NEEDS_REVISION write, this exact input
    would append a record for a feature that does not exist UNLESS the
    existence guard is extended to cover NEEDS_REVISION too -- this test pins
    that extension must happen alongside DD-1, not after it.
    """
    repo = tmp_path / "repo"
    feature_id = "declared-facts-at4-imaginary-fixture"

    # A real, correctly-tagged .feature scenario -- AT derivation succeeds --
    # but deliberately NO docs/feature/{feature_id}/feature-delta.md.
    _write_real_feature_scenario(repo, feature_id)
    assert not (repo / "docs" / "feature" / feature_id).exists(), (
        "test setup invariant: the imaginary feature's docs/feature "
        "directory must not exist -- if it does, the fixture is not "
        "testing the imaginary-slice case"
    )

    exit_code, stdout, stderr = _run_producer(
        repo,
        _base_argv(
            feature_id=feature_id,
            slice_id=_SLICE_ID,
            repo_root=repo,
            verdict="NEEDS_REVISION",
        ),
    )

    assert exit_code != 0, (
        "recording a NEEDS_REVISION verdict for a feature with NO "
        f"docs/feature/{feature_id}/feature-delta.md must be REFUSED "
        f"(non-zero exit) -- got exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}. The existence guard "
        "(`_verify_feature_slice_exists`) must extend to the NEEDS_REVISION "
        "path once that path starts writing ledger records (DD-1), or an "
        "imaginary feature/slice can be certified as reviewed."
    )

    records = _read_verdict_records(repo, feature_id, _SLICE_ID)
    assert records == [], (
        "an imaginary feature/slice must NEVER produce an ATReviewVerdict "
        f"ledger record, for ANY verdict -- got {records!r} "
        f"(exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r})."
    )
