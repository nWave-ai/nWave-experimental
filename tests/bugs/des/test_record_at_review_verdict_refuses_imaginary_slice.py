"""Regression (silent-false-cert, class #185/#126): `des record-at-review-
verdict` writes an APPROVED `ATReviewVerdict` record for an IMAGINARY
feature/slice -- one with no `docs/feature/{feature_id}/feature-delta.md` at
all, and no Slice Plan row naming `slice_id`.

DEFECT (RCA, grounded [read-in-code]): on an APPROVED verdict, `main()`
(`src/des/cli/at_review_verdict.py:402-504`) calls `_slice_at_derivation`
(lines 276-336) to compute `(at_ids, at_content_hash)`, then unconditionally
calls `record_review_outcome` -> `record_at_review_verdict` (lines 59-102,
136-187) to append the record to
`.nwave/telemetry/atdd-pure/{feature_id}.jsonl`. Neither `_slice_at_derivation`
(default `at_kind="gherkin"`) nor `main`/`record_review_outcome` ever checks
that `docs/feature/{feature_id}/feature-delta.md` exists, nor that `slice_id`
is a row in its `[REF] Slice Plan` table.

Confirmed mechanism: for `at_kind="gherkin"`, `_slice_at_derivation` calls
`carpaccio_slice_gate.parse_scenarios(carpaccio_format.read_feature_files
(repo_root, feature_id))` (line 330-332) -- `read_feature_files` ->
`feature_at_files.feature_tag_files` (`src/des/application/feature_at_files.py`
:64-89) returns `[]` (no exception) when zero `.feature` files
self-identify with `@feature-{feature_id}`. `parse_scenarios([])` returns
`[]`, so `slice_scenarios` is `[]` and `at_ids = []` -- a well-formed but
EMPTY derivation, not an error. `main()` proceeds to write the APPROVED
record with `at_ids: []` as if the feature/slice were real. The AT-completion
ledger -- the record-of-truth `carpaccio-slice-gate` (assertion 5) trusts to
gate a slice's `A_GREEN` entry -- is silently populated for a slice that was
never designed, never reviewed, and does not exist on disk.

THE FIX (crafter's job, NOT implemented here -- test-authoring only, zero
`src/` edits): before writing the APPROVED record, `record-at-review-verdict`
must validate that `docs/feature/{feature_id}/feature-delta.md` exists AND
that `slice_id` resolves to a row in its `[REF] Slice Plan` (e.g. via
`carpaccio_format.parse_slice_plan`); if either check fails, it must refuse
(non-zero exit / INDETERMINATE) with a what/why/how diagnostic, writing NO
record. A real feature/slice (feature-delta present, slice_id a Slice Plan
row) must be unaffected -- see the no-overcorrection guard below.

Driving surface (Mandate 13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.at_review_verdict.main(argv)` CLI EDGE, driven in-process
via `tests.common.in_process_cli.run_cli_in_process` (the in-process analogue
of the `des record-at-review-verdict ...` dispatcher invocation) under an
isolated `tmp_path` repo -- never the real `.nwave/telemetry/`.

RED-for-right-reason: today the positive AT below fails with a genuine
semantic `AssertionError` -- the CLI runs to completion, exits 0, and writes
a real `ATReviewVerdict` record for `feature_id="ghost"` (which has no
feature-delta.md at all) -- never an import/collection error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.at_review_verdict import main as record_at_review_verdict_main
from tests.common.in_process_cli import run_cli_in_process


_SLICE_ID = "slice-01"


def _run_record_at_review_verdict(
    repo_root: Path, argv: list[str]
) -> tuple[int, str, str]:
    """Drive the REAL `des record-at-review-verdict` CLI EDGE in-process."""
    return run_cli_in_process(argv, cwd=repo_root, main=record_at_review_verdict_main)


def _base_argv(*, feature_id: str, slice_id: str, repo_root: Path) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        "APPROVED",
        "--reviewer-agent-id",
        "nw-acceptance-designer-reviewer",
        "--repo-root",
        str(repo_root),
    ]


def _read_approved_records(
    repo_root: Path, feature_id: str, slice_id: str
) -> list[dict[str, object]]:
    """Every `ATReviewVerdict` record on the ledger for `feature_id`/`slice_id`.

    Reading the ledger itself (rather than only checking file-existence) is
    deliberate: a fix that creates the ledger file but still writes a hollow
    record would otherwise slip past a bare "file absent" check.
    """
    ledger_path = (
        repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    if not ledger_path.exists():
        return []
    return AtCompletionLedger(feature_id, repo_root).read_records(
        event_type="ATReviewVerdict", slice_id=slice_id
    )


def _write_real_feature_delta_with_slice_01(feature_delta_path: Path) -> None:
    """Minimal, realistic `feature-delta.md`: a `[REF] Slice Plan` table
    (canonical 5-column shape, `carpaccio_format.SLICE_PLAN_CANONICAL_COLUMNS`)
    carrying a genuine `slice-01` row -- mirrors the shape
    `test_record_at_review_verdict_rust_regression_at_kind.py` and the
    carpaccio gate's own fixtures use.
    """
    feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
    feature_delta_path.write_text(
        "# Feature Delta: real-feat\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | customer sees confirmation | done | | |\n",
        encoding="utf-8",
    )


def _write_real_feature_scenario(feature_file_path: Path, feature_id: str) -> None:
    """A real `.feature` file self-identifying with `@feature-{feature_id}`
    and carrying one `@slice-01`-tagged scenario -- the fixture
    `_slice_at_derivation`'s default `at_kind="gherkin"` path actually reads.
    """
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


# ===========================================================================
# 1. POSITIVE -- active-RED today: an imaginary feature/slice (no
#    feature-delta.md at all) must be REFUSED, never silently certified.
# ===========================================================================


def test_record_at_review_verdict_refuses_and_writes_no_record_for_imaginary_slice(
    tmp_path: Path,
) -> None:
    """`des record-at-review-verdict --feature-id ghost --slice-id slice-01
    --verdict APPROVED` against a tmp repo with NO
    `docs/feature/ghost/feature-delta.md` must REFUSE (non-zero exit) and
    must NEVER write an `ATReviewVerdict` record to
    `.nwave/telemetry/atdd-pure/ghost.jsonl`.

    Today: the CLI has no feature/slice-existence check at all, so it runs to
    completion, exits 0, and writes a real APPROVED record with `at_ids: []`
    for a feature that does not exist on disk -- the silent-false-cert this
    regression test pins against.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    feature_id = "ghost"

    # Deliberately absent: no docs/feature/ghost/feature-delta.md, no
    # .feature file anywhere tagged @feature-ghost. This IS the imaginary
    # feature/slice the defect lets through.
    assert not (repo / "docs" / "feature" / feature_id).exists(), (
        "test setup invariant: the ghost feature's docs/feature directory "
        "must not exist -- if it does, the fixture is not testing the "
        "imaginary-slice case"
    )

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(feature_id=feature_id, slice_id=_SLICE_ID, repo_root=repo),
    )

    assert exit_code != 0, (
        "recording an APPROVED verdict for a feature with NO "
        "docs/feature/ghost/feature-delta.md must be REFUSED (non-zero "
        f"exit) -- got exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}. `des record-at-review-verdict` has no "
        "feature/slice-existence check today (see this test module's "
        "docstring for the RCA + fix direction), so it currently exits 0 "
        "and certifies an imaginary slice."
    )

    records = _read_approved_records(repo, feature_id, _SLICE_ID)
    assert records == [], (
        "an imaginary feature/slice (no feature-delta.md, no Slice Plan "
        "row) must NEVER produce an ATReviewVerdict ledger record -- got "
        f"{records!r} (exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}). This is the silent-false-cert defect "
        "(class #185/#126): the ledger `carpaccio-slice-gate` trusts to "
        "gate A_GREEN entry was populated for a slice that does not exist."
    )


# ===========================================================================
# 2. NEGATIVE (no-overcorrection guard) -- a REAL feature/slice (a genuine
#    feature-delta.md with slice-01 in its Slice Plan, plus a real .feature
#    scenario) must still record its APPROVED verdict. The fix must add a
#    validation, never a blanket rejection.
# ===========================================================================


@pytest.mark.negative_at
def test_record_at_review_verdict_real_feature_slice_still_records_approved(
    tmp_path: Path,
) -> None:
    """A real feature (`docs/feature/real-feat/feature-delta.md` with a
    genuine `slice-01` Slice Plan row, plus a `.feature` file tagged
    `@feature-real-feat` carrying a `@slice-01` scenario) must still record
    its APPROVED verdict (exit 0, one ledger record) -- the validation added
    to fix the imaginary-slice defect above must NEVER reject a real
    feature/slice. Already GREEN today (no overcorrection risk yet, since no
    validation exists at all) -- pinned so the fix cannot regress it.
    """
    repo = tmp_path / "repo"
    feature_id = "real-feat"
    _write_real_feature_delta_with_slice_01(
        repo / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    _write_real_feature_scenario(
        repo / "tests" / "acceptance" / feature_id / "slice-01.feature",
        feature_id,
    )

    exit_code, stdout, stderr = _run_record_at_review_verdict(
        repo,
        _base_argv(feature_id=feature_id, slice_id=_SLICE_ID, repo_root=repo),
    )

    assert exit_code == 0, (
        "a REAL feature/slice (feature-delta.md present, slice-01 a genuine "
        "Slice Plan row, a real tagged .feature scenario) must still record "
        f"successfully (exit 0) -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}. A fix for the imaginary-"
        "slice defect must add a validation, never a blanket rejection."
    )

    records = _read_approved_records(repo, feature_id, _SLICE_ID)
    assert len(records) == 1, (
        "expected exactly one ATReviewVerdict record for the real "
        f"feature/slice -- got {records!r}"
    )
    at_ids = records[0].get("at_ids")
    assert isinstance(at_ids, list) and len(at_ids) == 1, (
        "the recorded verdict's at_ids must reflect the one real @slice-01 "
        f"scenario -- got at_ids={at_ids!r}"
    )
