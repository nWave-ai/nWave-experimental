"""Regression (F-SLICE-PLAN-STATUS-COLUMN-NEVER-SYNCED, backlog.md): `des
commit-slice` and `des feature-end run` both APPEND to the AT-completion
ledger (`.nwave/telemetry/atdd-pure/<feature-id>.jsonl`) on success, but
NEITHER writes back to the feature-delta.md `[REF] Slice Plan` markdown
table's `Status` column -- so a slice that is genuinely `SliceCommitVerified`
(or a feature that is genuinely feature-end-sealed) can sit on disk with a
stale `pending` row indefinitely.

FIX (backlog's own preferred option (a)): a producing-tool step -- both
`commit_slice.py` and `feature_end.py`, on success, mechanically flip the
corresponding Slice-Plan row (`pending -> shipped`), and `feature_end.py`
additionally appends a feature-end-sealed marker.

Driving surface: the CLI-layer wiring functions THEMSELVES
(`commit_slice._sync_slice_plan_status`, `feature_end._sync_feature_delta_
on_feature_end`) -- these are the exact producing-tool call sites wired into
`main()`'s success path (see `commit_slice.py` Step 6.5, `feature_end.py`'s
`_run_cycle`/`_run_batch`). Testing them directly (not via a full git-repo
`main()` invocation, already exhaustively covered by
`tests/des/integration/test_commit_slice.py` and the `feature-end` acceptance
suite) isolates THIS fix's own behavior without re-paying the heavy git-repo
harness cost for a markdown-only side effect.

The underlying pure text transforms (`carpaccio_format.mark_slice_status_
shipped` / `mark_feature_end_sealed`) are unit-tested separately in
`tests/des/unit/cli/test_carpaccio_format_slice_plan_status_sync.py`.

SAFETY GUARDRAILS under test (the dispatch's own hard constraints):
  * idempotent -- calling twice is a no-op the second time;
  * missing feature-delta.md (a bugfix, no Slice Plan) is a SILENT no-op,
    never raises;
  * a malformed/hand-edited table degrades LOUD (a caught exception prints
    a WARNING) but never raises out of the sync function -- the primary
    commit/feature-end operation is never blocked by this side effect.
"""

from __future__ import annotations

from pathlib import Path

from des.cli.carpaccio_format import FEATURE_END_SEALED_MARKER
from des.cli.commit_slice import _sync_slice_plan_status
from des.cli.feature_end import _sync_feature_delta_on_feature_end


_FEATURE_DELTA_TEMPLATE = """# Feature Delta — {feature_id}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|----------------|
| slice-01 | First slice value | pending | @walking_skeleton | reason one |
| slice-02 | Second slice value | pending | depends-on slice-01 | reason two |
"""


def _write_feature_delta(repo: Path, feature_id: str, text: str) -> Path:
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    delta_path = delta_dir / "feature-delta.md"
    delta_path.write_text(text, encoding="utf-8")
    return delta_path


# ---------------------------------------------------------------------------
# commit_slice._sync_slice_plan_status
# ---------------------------------------------------------------------------


def test_commit_slice_sync_flips_the_committed_slice_to_shipped(
    tmp_path: Path,
) -> None:
    feature_id = "some-feature"
    delta_path = _write_feature_delta(
        tmp_path, feature_id, _FEATURE_DELTA_TEMPLATE.format(feature_id=feature_id)
    )

    _sync_slice_plan_status(tmp_path, feature_id, ["slice-01"])

    text = delta_path.read_text(encoding="utf-8")
    slice_01_line = next(
        line for line in text.splitlines() if line.startswith("| slice-01")
    )
    assert "| shipped |" in slice_01_line
    # slice-02 is untouched -- only the committed slice flips.
    slice_02_line = next(
        line for line in text.splitlines() if line.startswith("| slice-02")
    )
    assert "| pending |" in slice_02_line


def test_commit_slice_sync_handles_multiple_slice_ids_in_one_batched_commit(
    tmp_path: Path,
) -> None:
    feature_id = "some-feature"
    delta_path = _write_feature_delta(
        tmp_path, feature_id, _FEATURE_DELTA_TEMPLATE.format(feature_id=feature_id)
    )

    _sync_slice_plan_status(tmp_path, feature_id, ["slice-01", "slice-02"])

    text = delta_path.read_text(encoding="utf-8")
    assert "pending" not in text
    assert text.count("| shipped |") == 2


def test_commit_slice_sync_is_a_silent_no_op_when_feature_delta_is_absent(
    tmp_path: Path,
) -> None:
    """A bugfix (or any dispatch with no feature-delta.md) must never crash
    or raise -- the primary commit already succeeded by the time this runs."""
    _sync_slice_plan_status(tmp_path, "no-such-feature", ["slice-01"])
    # No exception -- the assertion IS that this line was reached.
    assert not (tmp_path / "docs" / "feature").exists()


def test_commit_slice_sync_is_idempotent(tmp_path: Path) -> None:
    feature_id = "some-feature"
    delta_path = _write_feature_delta(
        tmp_path, feature_id, _FEATURE_DELTA_TEMPLATE.format(feature_id=feature_id)
    )

    _sync_slice_plan_status(tmp_path, feature_id, ["slice-01"])
    once = delta_path.read_text(encoding="utf-8")
    _sync_slice_plan_status(tmp_path, feature_id, ["slice-01"])
    twice = delta_path.read_text(encoding="utf-8")

    assert once == twice


def test_commit_slice_sync_never_raises_on_a_malformed_table(
    tmp_path: Path,
) -> None:
    feature_id = "some-feature"
    malformed = (
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|----------------|\n"
        "| not-a-slice-id | value | pending | | |\n"
    )
    delta_path = _write_feature_delta(tmp_path, feature_id, malformed)
    original = delta_path.read_text(encoding="utf-8")

    _sync_slice_plan_status(tmp_path, feature_id, ["slice-01"])

    # Degrade-quiet: the table was never rewritten (no matching row), and
    # the malformed content is untouched -- never a crash, never corruption.
    assert delta_path.read_text(encoding="utf-8") == original


def test_commit_slice_sync_never_clobbers_an_already_shipped_row(
    tmp_path: Path,
) -> None:
    feature_id = "some-feature"
    text = _FEATURE_DELTA_TEMPLATE.format(feature_id=feature_id).replace(
        "| slice-02 | Second slice value | pending |",
        "| slice-02 | Second slice value | shipped |",
    )
    delta_path = _write_feature_delta(tmp_path, feature_id, text)
    original = delta_path.read_text(encoding="utf-8")

    _sync_slice_plan_status(tmp_path, feature_id, ["slice-02"])

    assert delta_path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# feature_end._sync_feature_delta_on_feature_end
# ---------------------------------------------------------------------------


def test_feature_end_sync_flips_every_declared_slice_and_seals(
    tmp_path: Path,
) -> None:
    feature_id = "some-feature"
    delta_path = _write_feature_delta(
        tmp_path, feature_id, _FEATURE_DELTA_TEMPLATE.format(feature_id=feature_id)
    )

    _sync_feature_delta_on_feature_end(tmp_path, feature_id)

    text = delta_path.read_text(encoding="utf-8")
    assert "pending" not in text
    assert text.count("| shipped |") == 2
    assert FEATURE_END_SEALED_MARKER in text


def test_feature_end_sync_is_idempotent(tmp_path: Path) -> None:
    feature_id = "some-feature"
    delta_path = _write_feature_delta(
        tmp_path, feature_id, _FEATURE_DELTA_TEMPLATE.format(feature_id=feature_id)
    )

    _sync_feature_delta_on_feature_end(tmp_path, feature_id)
    once = delta_path.read_text(encoding="utf-8")
    _sync_feature_delta_on_feature_end(tmp_path, feature_id)
    twice = delta_path.read_text(encoding="utf-8")

    assert once == twice
    assert once.count(FEATURE_END_SEALED_MARKER) == 1


def test_feature_end_sync_is_a_silent_no_op_when_feature_delta_is_absent(
    tmp_path: Path,
) -> None:
    """A bugfix's feature-end (no feature-delta.md / no Slice Plan owed)
    must never crash -- the cycle's own FeatureEndReviewVerdict record has
    already been minted by the time this side effect runs."""
    _sync_feature_delta_on_feature_end(tmp_path, "no-such-feature")
    assert not (tmp_path / "docs" / "feature").exists()


def test_feature_end_sync_still_seals_a_feature_delta_with_no_slice_plan(
    tmp_path: Path,
) -> None:
    """A feature-delta with no `[REF] Slice Plan` section at all (e.g. a
    non-slice-plan-mode feature) still gets the feature-end-sealed marker
    -- the two concerns (per-slice Status sync, feature-end sealing) are
    independent."""
    feature_id = "no-slice-plan-feature"
    delta_path = _write_feature_delta(
        tmp_path, feature_id, "# Feature Delta — no-slice-plan-feature\n\nProse only.\n"
    )

    _sync_feature_delta_on_feature_end(tmp_path, feature_id)

    assert FEATURE_END_SEALED_MARKER in delta_path.read_text(encoding="utf-8")
