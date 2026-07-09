"""Regression: the feature-end truncation oracle recognizes a slice attested
by a `SliceCommitVerified` ledger record as DELIVERED.

THE BUG (feature-end-attests-pytest-regression, CRITICAL): `_undelivered_
slice_plan_slices` recognizes a Slice-Plan slice as delivered only via a
`@slice-NN`-tagged `.feature` file (gherkin) OR an attested `SliceProseDelivered`
ledger record (prose). A pytest-regression feature -- whose slices are attested
by `SliceCommitVerified` records, no `.feature` file, no `SliceProseDelivered`
-- has NEITHER recognized form, so every slice is flagged undelivered and
`des feature-end run` refuses with TRUNCATED forever (a pytest-regression
feature can never reach FeatureEnd).

THE FIX (design contract, docs/feature/feature-end-attests-pytest-regression/
feature-delta.md, corrected 2026-07-09): add a THIRD delivery-recognition form
-- a slice carrying a `SliceCommitVerified` ledger record is DELIVERED,
regardless of `at_kind`. `SliceCommitVerified` IS the un-gameable delivery
attestation: the spine emits it ONLY after the slice's E1+E2 commit gate passes
(the test existed AND passed on the committed tree). Recognizing ANY such record
(not an `at_kind`-specific subset) handles existing records with zero backfill,
since today's `SliceCommitVerified` records carry no `at_kind` field. Additive:
gherkin + prose recognition are unchanged; a declared slice with NONE of the
three forms is still truncated.

Active-RED (Mandate-7 / ADR-025): every SliceCommitVerified-recognition scenario
calls `_undelivered_slice_plan_slices` directly against a fixture project (a
Slice-Plan feature-delta + a hand-written AT-completion ledger of plain
`SliceCommitVerified` records) and asserts the POST-FIX behaviour -- it fails
for the right reason (AssertionError) against today's code, which recognizes
only gherkin + prose. The negative/regression controls assert already-correct
behaviour and PASS.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.cli.verify_deliver_integrity import _undelivered_slice_plan_slices


_TWO_SLICE_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | first delivered slice | pending | | j |
| slice-02 | second delivered slice | pending | | j |
"""

_ONE_SLICE_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | the only slice | pending | | j |
"""


def _seed_slice_plan(tmp_path: Path, feature_id: str, plan: str) -> None:
    feature_dir = tmp_path / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        plan.format(fid=feature_id), encoding="utf-8"
    )


def _write_ledger(tmp_path: Path, feature_id: str, records: list[dict]) -> None:
    ledger = tmp_path / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


def _slice_commit_verified(slice_id: str) -> dict:
    """The real `SliceCommitVerified` record shape today: event + slice_id, no
    `at_kind` field (the spine reads `args.at_kind` for gate-selection but never
    persists it -- so the recognition must key on the record's presence alone)."""
    return {"event": "SliceCommitVerified", "slice_id": slice_id}


def _seed_gherkin_feature_file(tmp_path: Path, feature_id: str, slice_id: str) -> None:
    """A `@feature-{id}`-tagged `.feature` file whose scenario carries `@slice-NN`.

    Mirrors the file/scenario tag contract `feature_at_files.feature_tag_files`
    + `slice_at_completeness.feature_files_for_slice` require: the file-level
    `@feature-{id}` tag precedes `Feature:`, and the `@slice-NN` tag is on the
    scenario (feature-level tags do not inherit).
    """
    acceptance_dir = tmp_path / "tests" / "des" / "acceptance" / feature_id
    acceptance_dir.mkdir(parents=True, exist_ok=True)
    (acceptance_dir / f"{slice_id}.feature").write_text(
        f"@feature-{feature_id}\n"
        f"Feature: {feature_id} delivers {slice_id}\n\n"
        f"  @{slice_id}\n"
        "  Scenario: the slice behaves\n"
        "    Given a precondition\n"
        "    When the behaviour runs\n"
        "    Then the outcome is observed\n",
        encoding="utf-8",
    )


def test_slice_commit_verified_slices_are_all_delivered(tmp_path: Path) -> None:
    # covers: R1
    """Scenario 1: EVERY declared slice carries a `SliceCommitVerified` record,
    no .feature, no SliceProseDelivered -> the oracle reports EMPTY (nothing
    undelivered)."""
    feature_id = "feature-end-attests-pytest-regression"
    _seed_slice_plan(tmp_path, feature_id, _TWO_SLICE_PLAN)
    _write_ledger(
        tmp_path,
        feature_id,
        [_slice_commit_verified("slice-01"), _slice_commit_verified("slice-02")],
    )

    undelivered = _undelivered_slice_plan_slices(tmp_path, feature_id)

    assert undelivered == [], (
        "a feature whose every Slice-Plan slice carries a SliceCommitVerified "
        f"record must NOT be flagged undelivered -- got {undelivered!r}"
    )


def test_declared_slice_with_no_delivery_form_is_never_recognized(
    tmp_path: Path,
) -> None:
    # covers: R2
    """NEGATIVE (the true floor): a declared slice with NONE of the three
    delivery forms -- no .feature, no SliceProseDelivered, no
    SliceCommitVerified -- is STILL flagged undelivered. The fix must not
    over-recognize."""
    feature_id = "feature-end-attests-pytest-regression"
    _seed_slice_plan(tmp_path, feature_id, _ONE_SLICE_PLAN)
    # No ledger at all -- nothing attests slice-01's delivery.

    undelivered = _undelivered_slice_plan_slices(tmp_path, feature_id)

    assert undelivered == ["slice-01"], (
        "a slice with no .feature file, no SliceProseDelivered record, and no "
        f"SliceCommitVerified record must stay TRUNCATED -- got {undelivered!r}"
    )


def test_mixed_plan_only_the_undelivered_slice_is_flagged(tmp_path: Path) -> None:
    # covers: R1, R2
    """Scenario 2: a MIXED plan -- slice-01 carries a SliceCommitVerified
    record (delivered), slice-02 carries nothing (undelivered) -> only
    slice-02 is returned."""
    feature_id = "feature-end-attests-pytest-regression"
    _seed_slice_plan(tmp_path, feature_id, _TWO_SLICE_PLAN)
    _write_ledger(tmp_path, feature_id, [_slice_commit_verified("slice-01")])

    undelivered = _undelivered_slice_plan_slices(tmp_path, feature_id)

    assert undelivered == ["slice-02"], (
        "only the slice carrying no delivery-form should be reported "
        f"undelivered -- got {undelivered!r}"
    )


def test_gherkin_feature_file_delivery_recognition_is_unaffected(
    tmp_path: Path,
) -> None:
    # covers: R3
    """Regression: a slice delivered by a `@slice-NN`-tagged `.feature` file
    (the pre-existing gherkin recognition form) is still NOT flagged
    undelivered -- the SliceCommitVerified fix is additive, gherkin recognition
    is byte-unchanged."""
    feature_id = "feature-end-attests-pytest-regression"
    _seed_slice_plan(tmp_path, feature_id, _ONE_SLICE_PLAN)
    _seed_gherkin_feature_file(tmp_path, feature_id, "slice-01")
    # No ledger -- delivery is attested purely by the .feature file's presence.

    undelivered = _undelivered_slice_plan_slices(tmp_path, feature_id)

    assert undelivered == [], (
        "a slice delivered by a @slice-NN-tagged .feature file must remain "
        f"recognized as delivered -- got {undelivered!r}"
    )


def test_mixed_delivery_forms_across_slices_all_recognized(tmp_path: Path) -> None:
    # covers: R1, R3
    """Breadth: one slice delivered via gherkin `.feature`, the other via a
    `SliceCommitVerified` record -- BOTH recognized forms compose in the SAME
    feature, nothing undelivered."""
    feature_id = "feature-end-attests-pytest-regression"
    _seed_slice_plan(tmp_path, feature_id, _TWO_SLICE_PLAN)
    _seed_gherkin_feature_file(tmp_path, feature_id, "slice-01")
    _write_ledger(tmp_path, feature_id, [_slice_commit_verified("slice-02")])

    undelivered = _undelivered_slice_plan_slices(tmp_path, feature_id)

    assert undelivered == [], (
        "gherkin-delivered slice-01 and SliceCommitVerified-attested slice-02 "
        f"must both be recognized as delivered -- got {undelivered!r}"
    )
