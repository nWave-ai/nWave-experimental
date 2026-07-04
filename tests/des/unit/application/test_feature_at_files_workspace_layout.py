"""Regression: ``feature_tag_files`` must not hardcode the search root to
``{repo}/tests``.

Diagnosed defect (Ale-approved RCA, no re-derivation): in
``src/des/application/feature_at_files.py``, ``feature_tag_files``:

* line 49 hardcodes ``tests_dir = repo / "tests"``;
* lines 50-51 return ``[]`` immediately when that exact directory is absent;
* line 55 rglobs ``*.feature`` ONLY under ``tests_dir``.

The ``@feature-{feature_id}`` tag-binding (``_file_feature_tags``) is already
layout-independent -- only the SEARCH ROOT is hardcoded. Consequence: a
feature whose ``.feature`` file lives in a workspace subdir (e.g.
``server/tests/acceptance/booking.feature``) is invisible to the carpaccio
gate, which rejects with the mute ``no-scenarios-for-slice`` verdict --
a message that names neither what was searched, where, nor how to fix it.

Approved fix (crafter's job, NOT implemented here): (1) generalize the
search root to rglob ``*.feature`` from the real repo root (excluding
``.git``, ``.venv``, ``node_modules``, ``__pycache__``, ``.pytest_cache``),
keeping the ``@feature-{id}`` tag filter -- backward-compatible with the
classic ``{repo}/tests/`` layout; (2) make the ``no-scenarios-for-slice``
refusal self-describing: name WHAT was searched (``.feature`` tagged
``@feature-{id}``), WHERE (the roots walked), HOW to fix, and the accepted
tag set.

This file authors the regression test ONLY -- it must NOT edit
``feature_at_files.py`` or ``carpaccio_format.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from des.application.feature_at_files import feature_tag_files
from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main


def _write_feature_file(
    path: Path, *, feature_id: str, scenario_slice_tag: str = "slice-01"
) -> Path:
    """Write a minimal, correctly file-tagged + scenario-tagged ``.feature``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: Booking\n\n"
        f"  @{scenario_slice_tag}\n"
        "  Scenario: Customer books a slot\n"
        "    Given a customer wants to book a slot\n"
        "    When the customer confirms the booking\n"
        "    Then the booking is confirmed\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Requirement 2 + 3 + 5: core workspace-subdir case, backward-compat guard,
# and a negative assertion -- combined via parametrize over layouts so the
# same fixture-and-assert shape sharpens coverage without inflation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "workspace_subdir",
    [
        pytest.param("tests", id="classic-repo-root-tests"),
        pytest.param("server/tests", id="workspace-subdir-server-tests"),
        pytest.param("packages/api/tests", id="nested-workspace-packages-api-tests"),
    ],
)
def test_feature_tag_files_finds_feature_across_workspace_layouts(
    tmp_path: Path, workspace_subdir: str
) -> None:
    """``feature_tag_files`` must find a correctly-tagged ``.feature`` file
    regardless of WHERE under the repo it lives -- not only under the
    hardcoded ``{repo}/tests`` root.

    ``workspace_subdir="tests"`` (classic layout) is the backward-compat
    guard (requirement 3): it PASSES both before and after the fix. The
    other two params are the diagnosed bug (requirement 2): they return
    ``[]`` at HEAD (RED) because ``tests_dir = repo / "tests"`` never
    matches a file under ``server/tests`` or ``packages/api/tests``.
    """
    repo = tmp_path / "repo"
    feature_id = "booking-flow"
    wanted = _write_feature_file(
        repo / workspace_subdir / "acceptance" / "booking.feature",
        feature_id=feature_id,
    )
    # Negative assertion (requirement 5): a sibling ``.feature`` file in the
    # SAME directory, tagged for a DIFFERENT feature, must never be returned
    # for this feature_id -- the tag filter, not just the root walk, gates
    # membership.
    _write_feature_file(
        repo / workspace_subdir / "acceptance" / "other-feature.feature",
        feature_id="unrelated-feature",
    )

    result = feature_tag_files(repo, feature_id)

    assert result == [wanted], (
        f"feature_tag_files(repo, {feature_id!r}) must return exactly the "
        f"file tagged '@feature-{feature_id}' under '{workspace_subdir}/', "
        f"got {result!r}"
    )


# ---------------------------------------------------------------------------
# Negative AT (GS-8): the over-match guard. Generalizing the search root to the
# whole repo introduces the risk of over-matching -- returning EVERY .feature
# in the tree regardless of tag. This negative AT locks the invariant that the
# generalized rglob stays TAG-SCOPED (returns only files tagged for THIS
# feature) and respects the prune of excluded dirs. The negative-named function
# satisfies `des verify-negative-at --all-critical` (name token `_not_`) and
# asserts the WRONG output (another feature's file / an excluded-dir file) is
# NOT produced. Likely GREEN at HEAD (HEAD under-matches under {repo}/tests, so
# it never wrongly returns others) and stays GREEN after the fix -- a negative
# AT that pins the invariant across the change.
# ---------------------------------------------------------------------------


def test_generalized_search_is_tag_scoped_and_does_not_over_match(
    tmp_path: Path,
) -> None:
    """The (to-be-generalized) repo-wide rglob must NOT return every ``.feature``
    in the tree -- only files tagged ``@feature-{feature_id}``.

    Two wrong outputs are asserted absent:

    * a ``.feature`` tagged for a DIFFERENT feature living under a workspace
      subdir -- the search must stay TAG-scoped, not root-scoped;
    * a ``.feature`` tagged for THIS feature but sitting under an EXCLUDED
      directory (``node_modules``) -- the prune must hold, so a vendored /
      generated tree cannot inject a phantom AT file.

    This is the real risk of the approved fix (over-matching); the negative AT
    locks it across the change.
    """
    repo = tmp_path / "repo"
    feature_id = "booking-flow"

    wanted = _write_feature_file(
        repo / "server" / "tests" / "acceptance" / "booking.feature",
        feature_id=feature_id,
    )
    # Wrong output #1: a different feature's file, correctly tagged for IT.
    other_feature_file = _write_feature_file(
        repo / "server" / "tests" / "acceptance" / "checkout.feature",
        feature_id="some-other-feature",
    )
    # Wrong output #2: a file tagged for THIS feature but under an excluded dir.
    excluded_dir_file = _write_feature_file(
        repo / "node_modules" / "vendored" / "phantom.feature",
        feature_id=feature_id,
    )

    result = feature_tag_files(repo, feature_id)

    # Pure negative assertions -- the WRONG output is never produced. Vacuously
    # true at HEAD (HEAD under-matches -> result is []); the load-bearing guard
    # is AFTER the fix generalizes the root: the other-feature file and the
    # excluded-dir file must STILL be absent. `wanted` is written only so the
    # tree contains a legitimately-tagged file the fix WOULD return -- this
    # negative AT never asserts it IS returned (that positive is the RED
    # parametrized test above); it only pins that the wrong ones are NOT.
    assert other_feature_file not in result, (
        "over-match: the tag-scoped search must NOT return a file tagged for a "
        f"DIFFERENT feature ({other_feature_file!r}); got {result!r}"
    )
    assert excluded_dir_file not in result, (
        "prune breach: a .feature under an excluded dir (node_modules) must "
        f"NOT be returned ({excluded_dir_file!r}); got {result!r}"
    )
    # The generalized rglob must never balloon to "every .feature in the tree"
    # (which would be 3 here) -- at most the single file tagged for THIS
    # feature and NOT under an excluded dir.
    assert len(result) <= 1, (
        "over-match: the search returned more than the single tag-scoped, "
        f"non-excluded file -- {result!r}"
    )
    assert all(p == wanted for p in result), (
        "every returned path must be the tag-scoped, non-excluded file "
        f"{wanted!r}; got {result!r}"
    )


# ---------------------------------------------------------------------------
# Requirement 4: the ``no-scenarios-for-slice`` refusal must be
# self-describing on GENUINE absence (no matching ``.feature`` anywhere).
# ---------------------------------------------------------------------------


_FEATURE_ID = "self-describing-refusal-fixture"


def _make_repo_with_slice_plan_no_feature_files(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        "# Feature Delta: self-describing-refusal fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | Customer books a slot | pending | | |\n",
        encoding="utf-8",
    )
    # Deliberately NO .feature file anywhere in the repo -- genuine absence.
    return repo


def test_no_scenarios_for_slice_refusal_is_self_describing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On genuine absence of any matching ``.feature`` file, the carpaccio
    gate's ``no-scenarios-for-slice`` refusal must name:

    * WHAT was searched -- ``.feature`` files tagged ``@feature-{feature_id}``;
    * WHERE it looked -- the root(s) walked;
    * HOW to fix it -- author/add a matching, correctly-tagged ``.feature``.

    At HEAD the refusal is mute: ``carpaccio_format._at_review_rejection``
    emits only ``"AT-review gate rejected slice {slice_id}: {reason}"`` --
    none of the three facts below. RED now; GREEN once the refusal is
    enriched with searched-root + tag + remediation content.
    """
    repo = _make_repo_with_slice_plan_no_feature_files(tmp_path)

    exit_code = carpaccio_gate_main(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            "slice-01",
            "--repo-root",
            str(repo),
        ]
    )

    stdout = capsys.readouterr().out
    payload: dict[str, object] = next(
        (
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ),
        {},
    )

    # The rejection mechanics (exit code + event + reason) are unaffected by
    # the fix -- pinned here so a future regression can't silently swap the
    # refusal class while still failing these content assertions.
    assert exit_code == 45
    assert payload.get("event") == "ATReviewGateRejected"
    assert payload.get("reason") == "no-scenarios-for-slice"

    combined = json.dumps(payload, sort_keys=True)

    assert f"@feature-{_FEATURE_ID}" in combined, (
        "refusal must name WHAT it searched for -- the "
        f"'@feature-{_FEATURE_ID}' tag -- payload was: {combined}"
    )
    assert re.search(r"search|walk", combined, re.IGNORECASE), (
        "refusal must name WHERE it looked (the root(s) walked) -- "
        f"payload was: {combined}"
    )
    assert re.search(r"\badd\b|creat|author", combined, re.IGNORECASE), (
        "refusal must name HOW to fix it (add/author a matching "
        f".feature file) -- payload was: {combined}"
    )
