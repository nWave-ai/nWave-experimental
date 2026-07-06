"""Pins two real gaps a deep-review found in the pytest-discovery leg of
``feature_files_for_slice`` (``des.application.slice_at_completeness``) --
the fix that made the oracle consult ``feature_at_files.feature_tagged_test_files``
/ ``resolve_test_file_attribution`` (carpaccio-pytest-at-comment-tag-binding,
WTBD-168) alongside its pre-existing Gherkin ``.feature`` discovery.

CONTRACT_SHAPE: bounded-change -- ``feature_files_for_slice`` must recognize
ONLY real, delivered AT artifacts (Gherkin ``.feature`` files and pytest test
files), and must report each delivered artifact EXACTLY ONCE, without
weakening the un-gameable truncation guard the sibling test module
(``test_feature_files_for_slice_pytest_discovery.py``) already pins.

Ground truth (read directly from
``src/des/application/feature_at_files.py``): ``feature_tagged_test_files``
walks EVERY file under the repo with NO filename/extension restriction --
``for dirpath, dirnames, filenames in os.walk(repo): ... path = Path(dirpath)
/ filename; if wanted in _file_head_window(path): matched.add(path)`` -- and
matches purely on a substring test against the file's first 20 lines
(``_HEAD_SCAN_LINES``). Two real defects follow mechanically from that
unrestricted walk:

  AT-D1 (BLOCKER): a NON-TEST file (a doc, an ADR, a README, any ``.md`` or
  non-``test_*`` ``.py``) whose head window happens to contain
  ``# @feature-{id}`` + ``# @slice-NN`` -- e.g. because it *documents* the
  tag convention -- is WRONGLY recognized by ``feature_tagged_test_files`` as
  delivering the slice. ``feature_files_for_slice`` then reports the slice
  delivered and the un-gameable truncation guard (``_undelivered_slice_plan_
  slices``, the ``des feature-end run`` seal oracle) FALSE-SEALS a genuinely
  undelivered slice. This is the un-gameable-guard test: a truncated feature
  must not seal merely because a doc mentions the tag convention.

  AT-D2: a Gherkin ``.feature`` file carrying both the file-level
  ``@feature-{id}`` tag and a scenario-level ``@slice-NN`` tag is matched by
  BOTH discovery paths -- the Gherkin path (``feature_tag_files`` + the
  whole-file ``_SLICE_TAG_RE`` scan) AND the pytest path (``feature_tagged_
  test_files`` has no extension filter, so it also walks ``.feature`` files;
  its head-window scan finds the SAME tags since Gherkin tags precede
  ``Feature:`` within the first 20 lines). ``feature_files_for_slice`` appends
  the match from each path into the same ``matched`` list and only
  ``sorted()``s it at the end -- ``sorted()`` does not deduplicate -- so the
  single ``.feature`` file is reported TWICE.

Active-RED (Mandate-7 / ADR-025): ``feature_files_for_slice`` is shipped,
unscaffolded production code -- the RED here is a genuine behavioral gap
(semantic ``AssertionError``), never an import/collection error. DELIVER
closes both gaps by restricting pytest discovery to genuine test artifacts
and deduping the unioned candidate set; this file is not touched by that
change.

Layer 6 unit/PBT composition level (per ``nw-test-design-mandates-
composition-contract`` induction table): the SUT is a pure, read-only
filesystem function -- ``(repo, slice_id, feature_id) -> list[str]`` -- no
side effects, no git dependency. Same reuse-first precedent as the sibling
module ``test_feature_files_for_slice_pytest_discovery.py``, located under
``tests/des/unit/application/`` (NOT the Mandate-13-restricted
``tests/des/unit/(?:domain|cli)/*`` path).
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


def _write_non_test_tagged_file(
    repo: Path, rel_path: str, feature_id: str, slice_id: str
) -> Path:
    """A NON-TEST file (doc/ADR/plain module) whose head window merely
    *mentions* the tag convention -- never a real test artifact."""
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @feature-{feature_id}\n"
        f"# @{slice_id}\n"
        "This file documents the head-comment tag convention used by "
        "carpaccio-pytest-at-comment-tag-binding; it is not a test and "
        "delivers nothing.\n"
    )
    return target


# ---------------------------------------------------------------------------
# AT-D1 -- a non-test file with the tags must NOT count as a delivered AT.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path",
    [
        "docs/notes.md",
        "src/foo/notes.py",
    ],
    ids=["markdown-doc", "non-test-python-module"],
)
def test_non_test_file_with_head_tags_is_not_counted_as_delivered_at(
    tmp_path: Path, rel_path: str
) -> None:
    """A non-test file (a doc, an ADR, a non-``test_*`` module) whose head
    window happens to carry ``@feature-{id}`` + ``@slice-NN`` -- e.g. because
    it documents the tag convention -- must NOT be recognized as delivering
    the slice's AT. ``feature_tagged_test_files`` walks every file with no
    filename/extension restriction and matches on a bare substring test, so
    today it WRONGLY counts this doc, false-sealing a genuinely undelivered
    (truncated) slice.
    """
    doc = _write_non_test_tagged_file(tmp_path, rel_path, _FEATURE_ID, _SLICE_ID)
    _write_feature_delta(tmp_path, _FEATURE_ID)

    found = feature_files_for_slice(tmp_path, _SLICE_ID, _FEATURE_ID)

    assert found == [], (
        "a non-test file whose head window merely mentions the tag "
        f"convention (got {doc}) must NOT count as delivering the slice; "
        f"found={found!r} -- feature_tagged_test_files has no filename/"
        "extension restriction and wrongly recognized it"
    )

    undelivered = _undelivered_slice_plan_slices(tmp_path, _FEATURE_ID)
    assert undelivered == [_SLICE_ID], (
        "the un-gameable truncation guard must still report the slice "
        f"TRUNCATED when only a non-test file carries the tags; got "
        f"undelivered={undelivered!r} -- a truncated feature must not "
        "false-seal because a doc mentions the tag convention"
    )


# ---------------------------------------------------------------------------
# AT-D2 -- a .feature file matched by BOTH discovery paths must appear ONCE.
# ---------------------------------------------------------------------------


def test_gherkin_feature_file_matched_by_both_paths_appears_once(
    tmp_path: Path,
) -> None:
    """A ``.feature`` file whose head carries the file-level
    ``@feature-{id}`` tag and a scenario-level ``@slice-NN`` tag is matched
    by BOTH the Gherkin discovery path (``feature_tag_files`` + the
    whole-file ``@slice-NN`` scan) AND the pytest discovery path
    (``feature_tagged_test_files`` applies no extension filter, so it also
    walks ``.feature`` files and finds the same tags within its head-window
    scan). ``feature_files_for_slice`` must return this file EXACTLY ONCE.
    """
    gherkin_at = _write_gherkin_at(tmp_path, _FEATURE_ID, _SLICE_ID)

    found = feature_files_for_slice(tmp_path, _SLICE_ID, _FEATURE_ID)

    assert len(found) == len(set(found)), (
        "a .feature file matched by BOTH the Gherkin path and the pytest "
        f"head-tag walk must appear ONCE, not duplicated; got found={found!r}"
    )
    assert found == [str(gherkin_at.relative_to(tmp_path))], (
        "expected exactly one entry for the doubly-matched Gherkin AT; got "
        f"found={found!r}"
    )
