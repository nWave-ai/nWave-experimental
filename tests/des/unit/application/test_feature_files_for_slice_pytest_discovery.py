"""Pins F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND (High beta-blocker).

CONTRACT_SHAPE: bounded-change -- ``feature_files_for_slice`` (application
layer) and its consumer ``_undelivered_slice_plan_slices`` (the feature-end
seal oracle) must ADD pytest-file discovery to their existing Gherkin-only
discovery WITHOUT weakening the un-gameable truncation guard.

Ground truth (Tsunami-verified via ``callers_of``, no invention):
``feature_files_for_slice`` (``des.application.slice_at_completeness``) is the
ONLY discovery used by ``missing_at_files`` (same module),
``_undelivered_slice_plan_slices`` (``des.cli.verify_deliver_integrity`` --
the ``des feature-end run`` seal oracle), and
``verify_slice_commit_completeness._effective_scope``. Today it walks ONLY
``feature_at_files.feature_tag_files`` (Gherkin ``.feature`` files by the
file-level ``@feature-{id}`` tag) -- a slice delivered exclusively by a
pytest test file is invisible to it, so ``des feature-end run`` REFUSES to
seal ANY pytest-AT-delivered feature, reporting ``FeatureSlicePlanPending``
(TRUNCATED), even though real active-RED pytest ATs exist on disk.

The pytest-side discovery ALREADY SHIPPED (carpaccio-pytest-at-comment-tag-
binding, WTBD-168): ``feature_at_files.feature_tagged_test_files`` walks test
files by a ``# @feature-{id}`` HEAD-COMMENT tag, and
``feature_at_files.resolve_test_file_attribution`` resolves a test file's
``@slice-NN`` / ``@covers-Rn`` sub-tags from the same head-comment window.
``feature_files_for_slice`` simply never consults them -- this test proves
that gap and pins the fix's observable contract.

Active-RED (Mandate-7 / ADR-025): ``feature_files_for_slice`` and
``_undelivered_slice_plan_slices`` are shipped, unscaffolded production code
-- the RED here is a genuine behavioral gap (semantic ``AssertionError`` on
the missing-recognition assertion), not an import/collection error. DELIVER
extends ``feature_files_for_slice`` to also consult the pytest resolvers;
this file is not touched by that change.

Layer 6 unit/PBT composition level (per ``nw-test-design-mandates-
composition-contract`` induction table): both SUTs are pure, read-only
filesystem functions -- ``(repo, slice_id, feature_id) -> list[str]`` and
``(project_dir, feature_id) -> list[str]`` respectively, no side effects, no
git dependency (``feature_files_for_slice``/``_undelivered_slice_plan_slices``
never call git; only the unrelated ``missing_at_files`` sibling does). A
pure-function correctness pin for an internal completeness-oracle bug is the
established reuse-first precedent for this exact SSOT
(``tests/des/acceptance/reverify_e1_via_scoped_wrapper/
test_slice_01_pure_function_scoping.py`` pins ``missing_at_files`` the same
way; ``tests/des/unit/cli/test_verify_integrity_prose_exemption.py`` pins a
sibling branch of ``_undelivered_slice_plan_slices`` the same way). Located
under ``tests/des/unit/application/`` -- NOT the Mandate-13-restricted
``tests/des/unit/(?:domain|cli)/*`` path.
"""

from __future__ import annotations

from pathlib import Path

from des.application.slice_at_completeness import feature_files_for_slice
from des.cli.verify_deliver_integrity import _undelivered_slice_plan_slices


_FEATURE_ID = "f-feature-end-completeness-oracle-pytest-blind"
_SLICE_ID = "slice-01"

_SLICE_PLAN_TABLE = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    f"| {_SLICE_ID} | pytest-AT-delivered oracle fix | shipped | @x | because |\n"
)


def _write_feature_delta(repo: Path, feature_id: str) -> None:
    path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Feature Delta: {feature_id}\n\n{_SLICE_PLAN_TABLE}")


def _write_tagged_pytest_at(repo: Path, feature_id: str, slice_id: str) -> Path:
    """A pytest AT file head-tagged for ``feature_id``/``slice_id`` -- NO ``.feature``."""
    target = repo / "tests" / feature_id / "acceptance" / f"test_{slice_id}.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @feature-{feature_id}\n"
        f"# @{slice_id}\n"
        "def test_delivers_the_slice():\n"
        "    assert True\n"
    )
    return target


def _write_gherkin_at(repo: Path, feature_id: str, slice_id: str) -> Path:
    target = repo / "tests" / feature_id / "acceptance" / f"{slice_id}.feature"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"@feature-{feature_id}\n"
        f"Feature: {feature_id} -- {slice_id}\n\n"
        f"  @{slice_id}\n"
        "  Scenario: ships its AT\n"
        "    Given a committed slice\n"
        "    When the gate runs\n"
        "    Then the slice is certified green\n"
    )
    return target


def _write_untagged_pytest_at(repo: Path, feature_id: str, slice_id: str) -> Path:
    """A pytest AT file carrying the ``@slice-NN`` sub-tag but NO ``@feature-{id}`` tag."""
    target = repo / "tests" / feature_id / "acceptance" / f"test_{slice_id}_untagged.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @{slice_id}\ndef test_delivers_the_slice():\n    assert True\n"
    )
    return target


# ---------------------------------------------------------------------------
# 1. POSITIVE -- a pytest-head-tagged AT (no .feature) is recognized as the
#    slice's delivered AT file.
# ---------------------------------------------------------------------------


def test_pytest_head_tagged_file_recognized_as_slice_delivery(tmp_path: Path) -> None:
    """A slice delivered ONLY by a ``@feature-{id} @slice-NN`` head-tagged pytest
    file must be discovered by ``feature_files_for_slice`` -- today it returns
    ``[]`` (Gherkin-only discovery), which is the exact defect this AT pins.
    """
    pytest_at = _write_tagged_pytest_at(tmp_path, _FEATURE_ID, _SLICE_ID)

    found = feature_files_for_slice(tmp_path, _SLICE_ID, _FEATURE_ID)

    assert str(pytest_at.relative_to(tmp_path)) in found, (
        "feature_files_for_slice must recognize a pytest AT head-tagged "
        f"'@feature-{_FEATURE_ID} @{_SLICE_ID}' as delivering the slice; "
        f"got found={found!r} (Gherkin-only discovery blind to pytest ATs)"
    )


# ---------------------------------------------------------------------------
# 2. The feature-end seal oracle must NOT flag a pytest-AT-delivered feature
#    TRUNCATED.
# ---------------------------------------------------------------------------


def test_feature_end_oracle_recognizes_pytest_delivered_slice(tmp_path: Path) -> None:
    """``_undelivered_slice_plan_slices`` (the ``des feature-end run`` seal
    oracle) must return ``[]`` for a feature whose only declared slice is
    delivered by a tagged pytest AT -- today it returns ``["slice-01"]``
    (TRUNCATED / ``FeatureSlicePlanPending``), blocking every pytest-AT
    infra/CLI feature's seal.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID)
    _write_tagged_pytest_at(tmp_path, _FEATURE_ID, _SLICE_ID)

    undelivered = _undelivered_slice_plan_slices(tmp_path, _FEATURE_ID)

    assert undelivered == [], (
        "a pytest-AT-delivered slice must not be reported TRUNCATED by the "
        f"feature-end seal oracle; got undelivered={undelivered!r}"
    )


# ---------------------------------------------------------------------------
# 3a. NO-REGRESSION -- the pre-existing Gherkin discovery path stays intact.
# ---------------------------------------------------------------------------


def test_gherkin_delivered_slice_still_recognized(tmp_path: Path) -> None:
    """A Gherkin-delivered slice (the pre-existing, already-working path)
    must remain recognized once pytest discovery is added -- an additive
    fix, never a replacement that could regress the Gherkin oracle.
    """
    gherkin_at = _write_gherkin_at(tmp_path, _FEATURE_ID, _SLICE_ID)

    found = feature_files_for_slice(tmp_path, _SLICE_ID, _FEATURE_ID)

    assert str(gherkin_at.relative_to(tmp_path)) in found, (
        "the pre-existing Gherkin .feature discovery path must be preserved; "
        f"got found={found!r}"
    )

    _write_feature_delta(tmp_path, _FEATURE_ID)
    undelivered = _undelivered_slice_plan_slices(tmp_path, _FEATURE_ID)
    assert undelivered == [], (
        "the feature-end oracle must still clear a Gherkin-delivered slice; "
        f"got undelivered={undelivered!r}"
    )


# ---------------------------------------------------------------------------
# 3b. NO-REGRESSION -- a slice with NEITHER a .feature NOR a tagged pytest
#     file MUST STILL be flagged TRUNCATED. The un-gameable truncation
#     oracle must not be weakened by the pytest-discovery addition.
# ---------------------------------------------------------------------------


def test_slice_with_no_at_of_any_kind_stays_truncated(tmp_path: Path) -> None:
    """A declared slice with no ``.feature`` file and no tagged pytest file
    is genuinely undelivered -- the fix must not accidentally widen
    discovery into a silent, un-gameable pass. This is the negative control
    proving the truncation guard survives the pytest-discovery addition.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID)
    # Deliberately write NOTHING under tests/{feature_id}/acceptance/.

    found = feature_files_for_slice(tmp_path, _SLICE_ID, _FEATURE_ID)
    assert found == [], (
        f"a slice with no AT of any kind must resolve to zero files; got {found!r}"
    )

    undelivered = _undelivered_slice_plan_slices(tmp_path, _FEATURE_ID)
    assert undelivered == [_SLICE_ID], (
        "a genuinely undelivered slice (no .feature, no tagged pytest file) "
        f"must still be reported TRUNCATED; got undelivered={undelivered!r} "
        "-- the un-gameable truncation oracle must not be weakened"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE -- a pytest file WITHOUT the @feature-{id} head-comment tag
#    must NOT count (no silent over-match; the tag is the discovery key).
# ---------------------------------------------------------------------------


def test_pytest_file_without_feature_tag_does_not_count(tmp_path: Path) -> None:
    """A pytest file carrying ``@slice-NN`` but no ``@feature-{id}`` head
    tag must be excluded from discovery -- the feature tag, not the slice
    tag alone, is what binds a file to THIS feature (wall W5 precedent:
    slice-ids are reused across features).
    """
    _write_untagged_pytest_at(tmp_path, _FEATURE_ID, _SLICE_ID)

    found = feature_files_for_slice(tmp_path, _SLICE_ID, _FEATURE_ID)

    assert found == [], (
        "a pytest file with no '@feature-{id}' head-comment tag must not be "
        f"discovered as delivering the slice (no silent over-match); got {found!r}"
    )
