"""Regression AT: `des commit-slice` self-validates the subject against gitlint.

RCA (GDP-6 producing-tool self-validation gap, task #37): ``des commit-slice``
builds a commit subject and creates the commit WITHOUT validating it against
the repo's own commit linter (``.gitlint``, gitlint 0.19.1 -- the SAME linter
CI's commitlint job runs). Two real CI reds landed from this in one session: a
subject whose description started with a digit (gitlint T7 --
``title-match-regex``: ``^(feat|fix|...)(\\(.+\\))?: [a-zA-Z].*$``), and a
102-char subject (gitlint T1 -- ``title-max-length=100``). The producing tool
must self-validate its output against the SAME linter the downstream gate
(CI commitlint) runs, and degrade LOUD BEFORE committing -- never emit a
commit CI will reject (GDP-6: no-silent-wrong).

This is a REGRESSION test, authored RED: it drives the REAL ``des
commit-slice`` entry point (``commit_slice_main``) against a real tmp git
work-tree (Mandate 6 -- subprocess/real-IO integration layer, mirrors
``test_commit_slice.py``'s harness) and pins the desired self-validation
contract. Today ``commit_slice.py`` has NO gitlint-aware subject check
anywhere between subject assembly (``main()``, message building) and the
``git commit`` call (``_commit_with_placeholder``) -- confirmed by a full
read of ``src/des/cli/commit_slice.py`` (zero occurrences of "gitlint" in
``src/des/``). Both negative scenarios below currently COMMIT the bad
subject (no refusal) -- RED for the right reason: the "no commit landed /
non-zero exit / diagnostic names the rule" assertions fail because
commit-slice does not yet perform this check.

Contract this AT pins (the crafter's fix must satisfy it):
  * A gitlint-COMPLIANT subject commits exactly as before (no behaviour
    change on the happy path).
  * A subject whose description starts with a DIGIT (violates T7 --
    title-match-regex) is REFUSED: no commit is created (HEAD unchanged),
    ``des commit-slice`` exits non-zero, and the emitted diagnostic names the
    violated rule (T7) and the fix (start the description with a letter).
  * A subject line LONGER than 100 characters (violates T1 --
    title-max-length) is REFUSED the same way, naming the length rule (T1 /
    the 100-char ceiling).
  * The refusal is an EARLY guard: it must fire before the (potentially
    slow, ~60-130s) build-tier verify, so a bad subject fails fast. This tmp
    repo carries no ``tests/build`` tier (see ``_init_repo``), so
    ``build_tier_exit_verdict`` is already a fast N/A here -- the assertions
    below are ordering-agnostic (they only require NO commit landed), but the
    early-guard placement is a load-bearing design constraint for the fix
    (see the docstring note above and the module header of
    ``commit_slice.py``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli.commit_slice import main as commit_slice_main
from tests.des._helpers.commit_slice_git_template import (
    provision_commit_slice_repo,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Provision the git work-tree via the shared session-cached template.

    See ``tests.des._helpers.commit_slice_git_template`` -- the base repo
    (``git init`` + config + the "base: walking skeleton" commit, six real
    ``git`` subprocess spawns) is built ONCE per test process and cached;
    this call materializes an independent filesystem copy at ``root``, so
    no test's later mutations can leak into another test's repo.
    """
    provision_commit_slice_repo(root)


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def test_commit_slice_commits_compliant_subject(tmp_path: Path, capsys) -> None:
    """A gitlint-COMPLIANT subject commits exactly as before (no regression)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "# @feature-commit-slice-subject-gitlint-validation\n"
        "# @slice-01\n"
        "def test_slice_new():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-subject-gitlint-validation",
            "--all",
            "--slice-id",
            "slice-01",
            "--message",
            "fix(gitlint-subject): compliant subject commits normally",
            # This hermetic tmp_path repo carries no `.feature` files (this
            # AT's real subject is commit-slice's OWN gitlint self-
            # validation, orthogonal to any Gherkin scenario), so the default
            # gherkin E2 leg refuses `no .feature file resolves ...
            # vacuously` (ADR-DES-001 pre-flight). Point E2 at a REAL
            # committed pytest file already staged above so the pre-flight
            # gets genuine observed evidence instead of a vacuous pass.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    head_after = _git(repo, "rev-parse", "HEAD").strip()
    assert head_after != head_before


def test_commit_slice_refuses_subject_starting_with_digit(
    tmp_path: Path, capsys
) -> None:
    """A subject description starting with a DIGIT (gitlint T7) is REFUSED.

    Reproduces the real CI incident: 'fix(hooks): 4 language:system hooks ...'
    violates gitlint's title-match-regex (T7), which requires the character
    right after 'type(scope): ' to be a letter. commit-slice must refuse
    BEFORE committing -- never emit a subject CI's commitlint will reject.

    SPEED (2026-07-20): the gitlint subject check
    (``_gitlint_subject_violation``) is a pure function of ``repo`` +
    ``message`` -- it only ever does ``(repo / ".gitlint").is_file()`` (False
    for a nonexistent path, degrading to the built-in default rules) and
    fires BEFORE any staging/commit call in ``main()`` (confirmed by reading
    ``commit_slice.py``: the check sits above every ``git`` invocation). No
    real git repo is provisioned -- ``repo`` is never created on disk, so
    ``not repo.exists()`` after the call is a strictly STRONGER proof than a
    real-git HEAD-unchanged check that no git mutation occurred.
    """
    repo = tmp_path / "repo"
    bad_subject = "fix(gitlint-subject): 4 configuration values were wrong"

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-subject-gitlint-validation",
            "--all",
            "--slice-id",
            "slice-01",
            "--message",
            bad_subject,
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0
    assert event["event"] != "SliceCommitted"

    diagnostic = json.dumps(event)
    assert "T7" in diagnostic
    assert "letter" in diagnostic.lower()

    # No commit landed -- the refusal is fail-closed. No repo was ever
    # provisioned, so its continued absence IS the "no git mutation" proof.
    assert not repo.exists()


def test_commit_slice_refuses_subject_exceeding_max_length(
    tmp_path: Path, capsys
) -> None:
    """A subject line LONGER than 100 chars (gitlint T1) is REFUSED.

    Reproduces the real CI incident: a 102-char subject violates gitlint's
    title-max-length=100 (T1). commit-slice must refuse BEFORE committing.

    SPEED (2026-07-20): same pure-classification shape as the T7 sibling
    above -- no real git repo is provisioned, see that test's docstring.
    """
    repo = tmp_path / "repo"
    long_subject = "fix(gitlint-subject): " + ("word " * 20)
    assert len(long_subject) > 100  # sanity: the fixture must actually violate T1

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "commit-slice-subject-gitlint-validation",
            "--all",
            "--slice-id",
            "slice-01",
            "--message",
            long_subject,
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0
    assert event["event"] != "SliceCommitted"

    diagnostic = json.dumps(event)
    assert "T1" in diagnostic
    assert "100" in diagnostic

    assert not repo.exists()
