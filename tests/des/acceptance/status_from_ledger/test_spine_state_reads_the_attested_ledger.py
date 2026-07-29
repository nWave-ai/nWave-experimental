"""A feature's spine state must be read where it is ATTESTED -- the ledger --
and the ledger's silence must never be dressed up as a state.

DEFECT (Mikado D52, ``docs/mikado/EXECUTION-SSOT-des-optimization.md``).
``feature_classifier`` already claims to derive the atdd_pure spine state from
telemetry: ``_is_atdd_pure`` reads ``_has_atdd_pure_telemetry(feature_dir)``
before falling back to a Slice Plan heading. That probe looks for
``{feature_dir}/.nwave/telemetry/atdd-pure/*.jsonl`` -- a ledger NESTED INSIDE
the feature directory. Measured on the live tree 2026-07-28: that path exists
for **0 of 376** feature directories, while **240 of 376** carry a ledger at
the real repo-root location ``{repo}/.nwave/telemetry/atdd-pure/{id}.jsonl``.
The branch has never returned True in production and no test exercised it, so
the classification rests entirely on the heading probe -- the
directory-as-database the node exists to remove.

WHY IT MATTERS: the consumer is not a report. ``convert_to_atdd_pure``'s
``_drain_blocker`` gates the batch classic->atdd_pure migration on this class
and treats everything that is not ``classic-needs-manual-review`` as safe to
proceed. A feature that IS on the atdd_pure spine -- with a ledger full of
attested records -- but whose markdown never carries the heading line is
classified ``pre-distill``. The migration then reasons about a feature whose
real state it never read.

MEASURED EVENT VOCABULARY -- what these ATs are allowed to key on. Counted
over the 3,400 records in the live ``.nwave/telemetry/`` tree, 2026-07-28:
``CarpaccioGateCleared`` 663, ``SliceCommitVerified`` 511, ``ATReviewVerdict``
437, ``FeatureEndPending`` 59, ``FeatureEndReviewVerdict`` 52,
``EBatchRefactorCompleted`` 52. A bare ``FeatureEnd`` event: **0 records and 0
producers** -- it is a name in prose, not an event. These ATs therefore key on
the PRESENCE OF AN ATTESTED RECORD, not on any single event name, and never on
``FeatureEnd``.

DESIGN, and the refusals it must produce:

1. The ledger is located by ANCHOR, never by a fixed number of ``..`` hops:
   the first ancestor of the feature directory that actually carries a
   ``.nwave/telemetry/atdd-pure`` directory is the ledger root. No new CLI
   flag, so ``des classify-features`` inherits the fix without an operator
   having to know it exists -- the previous nested-path version was
   catalogued but never wired, and a flag nobody passes would repeat that.

2. A ledger that does not exist attests nothing, and absence is NOT a state:
   the classification falls back to the directory probes unchanged. No default
   spine state is manufactured out of a missing file.

3. A ledger that exists but attests nothing readable (empty file, or lines
   that carry no ``event``) is INDETERMINATE, not negative. It resolves to
   ``classic-needs-manual-review`` -- the class the module already reserves
   for "cannot decide" -- so the third state reaches the manifest aggregate
   instead of collapsing into the negative branch (GDP-8 arity corollary).

WHAT THESE ATs DELIBERATELY DO NOT PIN: they do not derive DONE-ness. A
"feature is sealed" predicate over ``FeatureEndReviewVerdict`` +
``EBatchRefactorCompleted`` already exists three times in ``scripts/`` and has
no consumer in ``src/``; adding a fourth definition here with no caller would
reproduce the very producer-without-reader pattern the Mikado tree condemns.

DRIVING SURFACE: every AT writes a real JSONL ledger file on disk in the real
repo-root shape and reads it back through the production ``classify`` /
``des classify-features`` path -- never by stubbing the probe.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from des.cli import classify_features
from des.domain import feature_classifier


if TYPE_CHECKING:
    from pathlib import Path


def _attested_record(feature_id: str) -> dict[str, object]:
    """One real-shaped ledger record naming an OBSERVED event."""
    return {
        "event": "SliceCommitVerified",
        "feature_id": feature_id,
        "gate": "commit-slice",
        "record_hash": "0" * 64,
        "seq": 1,
        "slice_id": "slice-01",
        "timestamp": "2026-07-28T18:17:57.229028Z",
    }


def _feature_dir(root: Path, feature_id: str) -> Path:
    """Create a roadmap-free feature directory carrying no Slice Plan heading."""
    feature_dir = root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    (feature_dir / "notes.md").write_text(
        "# Notes\n\nNo Slice Plan heading here.\n", encoding="utf-8"
    )
    return feature_dir


def _ledger_dir(root: Path) -> Path:
    """The real repo-root ledger location."""
    ledger_dir = root / ".nwave" / "telemetry" / "atdd-pure"
    ledger_dir.mkdir(parents=True)
    return ledger_dir


def _write_ledger(
    ledger_dir: Path, feature_id: str, *records: dict[str, object]
) -> None:
    """Write a real per-feature JSONL ledger -- one JSON object per line."""
    lines = "".join(json.dumps(record) + "\n" for record in records)
    (ledger_dir / f"{feature_id}.jsonl").write_text(lines, encoding="utf-8")


def test_an_attested_repo_root_ledger_classifies_the_feature_atdd_pure(
    tmp_path: Path,
) -> None:
    """Given a roadmap-free feature with NO Slice Plan heading in any markdown,
    and a repo-root ledger carrying one attested record for that feature id,
    When the feature is classified,
    Then it is `atdd_pure` -- the state is read where it is attested.
    """
    feature_dir = _feature_dir(tmp_path, "ledger-attested")
    _write_ledger(
        _ledger_dir(tmp_path), "ledger-attested", _attested_record("ledger-attested")
    )

    assert feature_classifier.classify(feature_dir) == feature_classifier.ATDD_PURE


def test_a_feature_without_a_ledger_is_not_given_a_default_spine_state(
    tmp_path: Path,
) -> None:
    """Given a ledger directory that holds no file for this feature,
    When the feature is classified,
    Then the ledger contributes nothing and the directory probes decide alone
    (`pre-distill`) -- absence never manufactures `atdd_pure`.
    """
    feature_dir = _feature_dir(tmp_path, "no-ledger")
    _ledger_dir(tmp_path)

    assert feature_classifier.classify(feature_dir) == feature_classifier.PRE_DISTILL


def test_another_features_ledger_never_attests_this_feature(tmp_path: Path) -> None:
    """Given a populated ledger directory whose only file belongs to a
    DIFFERENT feature,
    When this feature is classified,
    Then it is `pre-distill`: attestation is keyed on the feature id, never on
    the ledger directory being non-empty.
    """
    feature_dir = _feature_dir(tmp_path, "unattested")
    _write_ledger(
        _ledger_dir(tmp_path), "some-other-feature", _attested_record("some-other")
    )

    assert feature_classifier.classify(feature_dir) == feature_classifier.PRE_DISTILL


def test_an_empty_ledger_is_never_read_as_evidence_of_not_being_on_the_spine(
    tmp_path: Path,
) -> None:
    """Given a ledger FILE that exists but carries zero records,
    When the feature is classified,
    Then the verdict is `classic-needs-manual-review` -- the explicit third
    state -- and NOT `pre-distill`, which would be a silent negative.
    """
    feature_dir = _feature_dir(tmp_path, "empty-ledger")
    (_ledger_dir(tmp_path) / "empty-ledger.jsonl").write_text("", encoding="utf-8")

    assert (
        feature_classifier.classify(feature_dir)
        == feature_classifier.CLASSIC_NEEDS_MANUAL_REVIEW
    )


def test_a_ledger_whose_records_name_no_event_never_attests_the_spine(
    tmp_path: Path,
) -> None:
    """Given a ledger whose lines parse as JSON but carry no `event` field,
    When the feature is classified,
    Then the verdict is `classic-needs-manual-review`: a record that names no
    event attests nothing, and that gap is surfaced rather than absorbed.
    """
    feature_dir = _feature_dir(tmp_path, "eventless-ledger")
    _write_ledger(
        _ledger_dir(tmp_path), "eventless-ledger", {"feature_id": "eventless-ledger"}
    )

    assert (
        feature_classifier.classify(feature_dir)
        == feature_classifier.CLASSIC_NEEDS_MANUAL_REVIEW
    )


def test_an_attested_ledger_never_overrides_the_roadmap_classic_binding(
    tmp_path: Path,
) -> None:
    """Given a feature that carries BOTH a classic `deliver/roadmap.json` and
    an attested repo-root ledger,
    When it is classified,
    Then the roadmap still binds it to the classic spine -- the ledger probe
    runs only on the roadmap-free branch (the S21 guard is preserved).
    """
    feature_dir = _feature_dir(tmp_path, "roadmap-bound")
    (feature_dir / "deliver").mkdir()
    (feature_dir / "deliver" / "roadmap.json").write_text(
        json.dumps({"phases": [{"id": "P1"}]}), encoding="utf-8"
    )
    _write_ledger(
        _ledger_dir(tmp_path), "roadmap-bound", _attested_record("roadmap-bound")
    )

    assert feature_classifier.classify(feature_dir) != feature_classifier.ATDD_PURE


def test_the_classify_features_cli_reads_the_repo_root_ledger_and_names_it(
    tmp_path: Path,
) -> None:
    """Given a feature whose only evidence of the atdd_pure spine is its
    repo-root ledger,
    When the real `des classify-features` CLI runs over the feature tree with
    the argv contract it already has (no new flag),
    Then the manifest classifies it `atdd_pure` AND names the ledger file the
    state was read from, so the operator can see WHERE state came from.
    """
    _feature_dir(tmp_path, "cli-attested")
    ledger_dir = _ledger_dir(tmp_path)
    _write_ledger(ledger_dir, "cli-attested", _attested_record("cli-attested"))
    manifest_path = tmp_path / "out" / "manifest.json"

    exit_code = classify_features.main(
        [
            "--features-root",
            str(tmp_path / "docs" / "feature"),
            "--out",
            str(manifest_path),
        ]
    )

    assert exit_code == 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(r for r in manifest["features"] if r["feature_id"] == "cli-attested")
    assert row["class"] == feature_classifier.ATDD_PURE
    assert row["ledger_path"] == str(ledger_dir / "cli-attested.jsonl")
