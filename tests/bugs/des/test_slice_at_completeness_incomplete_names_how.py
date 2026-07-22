"""Regression (GDP-3/GDP-4): `check-slice-at-completeness`'s `incomplete`
verdict must carry a `how` field naming the producing tool, not ONLY
``{slice_id, feature_id, commit, missing, verdict}`` (WHAT, no HOW).

Charter: ``docs/product/expectations/fix-slice-at-completeness-incomplete-how/
the-incomplete-verdict-names-how-to-land-the-missing-at-files.md``.

Found in ``src/des/cli/check_slice_at_completeness.py`` ``main()``:
  * ``:104`` -- the ``incomplete`` verdict (the slice commit omits one of the
    slice's declared ``.feature`` AT files) emits
    ``{slice_id, feature_id, commit, missing, verdict}`` with NO ``how``.
  * ``:94`` -- the ``MalformedInput`` path (exit 2, repo unreadable) likewise
    has no ``how``; the charter names it too but this AT does not pin it
    (dispatch scope: 1 positive + 1 negative on the ``incomplete`` path).

The fix direction (charter, NOT implemented here): ``incomplete`` -> HOW
routes to ``des commit-slice`` (stages + commits the slice, landing the
missing ``.feature`` files into the slice commit).

CRITICAL CONSTRAINT (preserved, do NOT change): the check stays intact -- an
incomplete slice commit is STILL rejected (exit 1); a complete slice commit
STILL clears (exit 0) with no spurious ``how``.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.check_slice_at_completeness.main()`` CLI driver, captured
via ``capsys`` -- mirrors the sibling regression AT
``tests/bugs/des/test_carpaccio_at_review_rejection_self_explains_how.py``
(the GDP-3/GDP-4 pattern this one follows).

Fixture: a real tmp git repo. ``missing_at_files`` (the SSOT,
``des.application.slice_at_completeness``) discovers a slice's ``.feature``
candidates by walking the WORKING TREE (``feature_tag_files``,
filesystem-based, not git-tracked-only) filtered by the file-level
``@feature-{feature_id}`` head tag preceding ``Feature:``, then checks
whether the inspected commit (or an ancestor) carries each candidate. A
``.feature`` file authored on disk but never staged/committed is exactly the
RCA Branch-A defect this gate exists to catch -- the fixture below builds
precisely that shape.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli.check_slice_at_completeness import main as check_completeness_main


_FEATURE_ID = "slice-at-completeness-how-fixture"
_SLICE_ID = "slice-01"

_FEATURE_FILE_TEXT = (
    f"@feature-{_FEATURE_ID}\n"
    "Feature: fixture feature\n\n"
    f"@{_SLICE_ID}\n"
    "Scenario: fixture scenario\n"
    "  Given a fixture precondition\n"
    "  When the fixture action occurs\n"
    "  Then the fixture outcome holds\n"
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _make_repo_missing_feature_file(tmp_path: Path) -> tuple[Path, str]:
    """A slice commit that OMITS the slice's declared ``.feature`` AT file.

    The initial (and only) commit carries an unrelated file. The
    ``.feature`` file is then written to disk -- found by
    ``feature_tag_files``'s working-tree walk -- but is deliberately never
    staged/committed: authored, never persisted (RCA Branch-A).
    """
    repo = tmp_path / "incomplete_repo"
    _git_init(repo)
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    commit = _commit_all(repo, "initial commit, no AT file")

    (repo / "slice.feature").write_text(_FEATURE_FILE_TEXT, encoding="utf-8")
    # Deliberately NOT git-added / committed.
    return repo, commit


def _make_repo_with_feature_file(tmp_path: Path) -> tuple[Path, str]:
    """A slice commit that CARRIES every ``.feature`` AT file the slice owns."""
    repo = tmp_path / "complete_repo"
    _git_init(repo)
    (repo / "README.md").write_text("fixture repo\n", encoding="utf-8")
    (repo / "slice.feature").write_text(_FEATURE_FILE_TEXT, encoding="utf-8")
    commit = _commit_all(repo, "initial commit, with AT file")
    return repo, commit


def _run_check(
    repo: Path, commit: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des check-slice-at-completeness`` CLI (``main()``)
    in-process, capturing its single-line JSON stdout payload via ``capsys``.
    """
    exit_code = check_completeness_main(
        [
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--slice-id",
            _SLICE_ID,
            "--feature-id",
            _FEATURE_ID,
        ]
    )
    stdout = capsys.readouterr().out
    lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    assert lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    payload: dict[str, object] = json.loads(lines[-1])
    return exit_code, payload


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_incomplete_verdict_names_a_how_routing_to_the_producing_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slice commit that omits the slice's declared ``.feature`` AT file is
    REJECTED (floor intact -- exit 1, ``verdict='incomplete'``, ``missing``
    non-empty) -- already true today. The payload must ALSO carry a ``how``
    field routing to the producing tool that lands the missing file into the
    slice commit (``des commit-slice``) -- this is MISSING today (RED for the
    right reason: a semantic assertion on the absent ``how``, not a crash or
    collection error).
    """
    repo, commit = _make_repo_missing_feature_file(tmp_path)

    exit_code, payload = _run_check(repo, commit, capsys)

    # Floor intact -- already passing today, must stay true after the fix.
    assert exit_code == 1, (
        "a slice commit missing a declared .feature AT file must still be "
        f"REJECTED (exit 1) -- got exit_code={exit_code}; payload={payload!r}"
    )
    assert payload.get("verdict") == "incomplete", payload
    missing = payload.get("missing")
    assert missing, f"expected a non-empty `missing` list, got payload={payload!r}"
    assert "slice.feature" in missing, payload

    # HOW -- MISSING today. check_slice_at_completeness.py:104 emits only
    # {slice_id, feature_id, commit, missing, verdict}; no `how` key exists.
    how = payload.get("how")
    assert how, (
        "the 'incomplete' verdict must carry a `how` field routing to the "
        "producing tool that lands the missing .feature files into the "
        f"slice commit -- payload carries no `how`: {payload!r}"
    )
    assert isinstance(how, str) and "commit-slice" in how, (
        "the `how` for an 'incomplete' verdict must route to `des "
        f"commit-slice` (stages + commits the slice) -- got how={how!r}"
    )


def _make_repo_taxonomy_blind(tmp_path: Path) -> tuple[Path, str]:
    """A commit carrying ZERO `.feature`/pytest-tagged AT candidates anywhere
    on the tree for this feature/slice -- taxonomy-blind (RCA
    fix-carpaccio-e1-vacuous-taxonomy-gap). Distinct from
    ``_make_repo_missing_feature_file``: that fixture authors a real
    candidate the check DISCOVERS but the commit fails to carry
    (``incomplete``, exit 1); this fixture has NO candidate to discover in
    the first place -- "nothing was checked", not "something was checked and
    found missing".
    """
    repo = tmp_path / "taxonomy_blind_repo"
    _git_init(repo)
    (repo / "README.md").write_text(
        "fixture repo, zero AT files anywhere\n", encoding="utf-8"
    )
    commit = _commit_all(repo, "initial commit, taxonomy-blind")
    return repo, commit


def test_indeterminate_verdict_when_taxonomy_finds_zero_at_candidates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RED (fix-carpaccio-e1-vacuous-taxonomy-gap): zero AT candidates found
    anywhere for the slice/feature under EITHER taxonomy (Gherkin
    ``@slice-NN`` or pytest ``@feature-{id}``/``@slice-NN``) must be reported
    INDETERMINATE (exit 3, ``verdict='indeterminate'``,
    ``event='SliceAtCompletenessIndeterminate'``) -- distinct from BOTH
    ``incomplete`` (exit 1, a real candidate the commit fails to carry) and
    ``MalformedInput`` (exit 2, repo/commit unreadable). Today the check
    conflates "nothing to verify" with "verified, nothing missing" and
    silently returns the SAME ``complete`` (exit 0) verdict as a genuinely
    complete slice.
    """
    repo, commit = _make_repo_taxonomy_blind(tmp_path)

    exit_code, payload = _run_check(repo, commit, capsys)

    assert exit_code == 3, (
        "zero recognized AT candidates anywhere must be reported "
        "INDETERMINATE (exit 3), never the silent false-green 'complete' "
        f"(exit 0) -- got exit_code={exit_code!r}; payload={payload!r}"
    )
    assert payload.get("verdict") == "indeterminate", payload
    assert payload.get("event") == "SliceAtCompletenessIndeterminate", payload


# ===========================================================================
# NEGATIVE AT -- control, green today AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_complete_verdict_never_carries_a_how(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slice commit that carries every ``.feature`` AT file the slice owns
    clears the check (``verdict='complete'``, exit 0) with NO spurious
    ``how`` in the payload -- the ``how`` remediation belongs only to the
    reject path, never leaking into a passing verdict. Must stay green both
    BEFORE and AFTER the fix.
    """
    repo, commit = _make_repo_with_feature_file(tmp_path)

    exit_code, payload = _run_check(repo, commit, capsys)

    assert exit_code == 0, (
        "a slice commit carrying every declared .feature AT file must clear "
        f"(exit 0) -- got exit_code={exit_code}; payload={payload!r}"
    )
    assert payload.get("verdict") == "complete", payload
    assert payload.get("missing") == [], payload
    assert "how" not in payload, (
        f"a 'complete' verdict must never carry a spurious `how` field: {payload!r}"
    )
