"""Regression (GDP-3): a bad-VALUE ``Slice-Id:`` trailer emits the
misleading "commit carries no Slice-Id:/Step-Id: trailer" error -- when the
trailer line IS present, only its value is not `slice-NN` form.

RCA (confirmed code-grounded; verified by a sister instance on a real cargo
repo -- ``Slice-Id: test-arm-a/slice-01`` said "no trailer" though git shows
it, costing a thrown examine + 2 hours). Locus:
``src/des/cli/verify_slice_commit_completeness.py``, ``_resolve_slice_ids``
(~line 612): it reads the commit message via ``git log -1 --format=%B``, then
calls ``extract_slice_ids`` (``src/des/domain/slice_id_trailer.py``), whose
regex ``_SLICE_ID_TRAILER_RE`` requires the trailer VALUE to already be in
`slice-NN` form. Git's OWN trailer parser is lenient (any `Key: value` line
in the trailing paragraph is a trailer) -- so a commit carrying
``Slice-Id: my-branch/slice-01`` (a REAL trailer line, non-slice-NN value):
git sees the trailer (confirmed below via
``git log --pretty=%(trailers:key=Slice-Id,valueonly)``), the strict regex
match fails, ``extract_slice_ids`` returns ``[]``, and ``_resolve_slice_ids``
collapses this into the SAME ``MalformedInput`` error as "no trailer at
all": "commit carries no Slice-Id:/Step-Id: trailer". The message is
misleading -- the commit DOES carry the trailer; only its value shape is
wrong.

The fix (crafter's job, NOT this test's): on an empty ``extract_slice_ids``
result, distinguish (a) a loose trailer line found (any value) -- name the
found value + the expected `slice-NN` form, from (b) no trailer line at all
-- keep the current "carries no trailer" message. The regex in
``slice_id_trailer.py`` is NOT touched (11 gates consume it, blast-radius
verified via tsunami) -- this test asserts on the CLI's emitted error only.

Driving surface: ``des.cli.verify_slice_commit_completeness.main(argv)``,
the CLI's real entry point (in-process, composition-root driving port),
against a REAL throwaway git repo built under ``tmp_path`` -- the observable
is the true one: what git's own trailer parser accepts, and what the gate's
stdout JSON says about it. ``main()`` prints one JSON line on stdout AND
stderr (``_emit``); this test captures stdout via ``capsys`` and reads the
LAST JSON line emitted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli.verify_slice_commit_completeness import main


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_repo_with_commit(repo: Path, commit_message: str) -> None:
    """Build a real, throwaway git repo with one commit carrying `commit_message`."""
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", commit_message)


def _last_json_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    """Parse the LAST single-line JSON event `main()` printed on stdout."""
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines, f"expected at least one JSON line on stdout, got: {captured.out!r}"
    return json.loads(lines[-1])


class TestVerifySliceCommitTrailerValueMessage:
    """RED-CONFIRMED regression: a bad-value trailer collapses into the
    absent-trailer error message; the two meanings must not collapse.
    """

    def test_bad_value_trailer_names_the_value_and_expected_form(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """POSITIVE (the bug, RED today): a commit carrying a REAL
        `Slice-Id:` trailer line whose VALUE is not `slice-NN` form must get
        an error that NAMES the found value and the expected `slice-NN`
        shape -- and must NOT collapse into the misleading "carries no
        Slice-Id:/Step-Id: trailer" message (the commit DOES carry one).
        """
        repo = tmp_path / "repo"
        bad_value = "my-branch/slice-01"
        _init_repo_with_commit(repo, f"do the thing\n\nSlice-Id: {bad_value}")

        # Confirm the fixture is honest: git's OWN trailer parser sees this
        # as a real trailer before the gate is ever invoked (the exact
        # leniency the RCA names as the root cause of the collapse).
        trailers = _run_git(
            repo, "log", "-1", "--pretty=%(trailers:key=Slice-Id,valueonly)"
        )
        assert bad_value in trailers, (
            "fixture setup broken: git's own trailer parser does not see "
            f"the Slice-Id: trailer -- got {trailers!r}"
        )

        exit_code = main(["--repo", str(repo), "--commit", "HEAD"])

        assert exit_code == 2, "malformed-input exit code expected (2)"
        event = _last_json_event(capsys)
        error = str(event.get("error", ""))
        assert bad_value in error, (
            "the emitted error must NAME the found bad-value trailer "
            f"{bad_value!r} -- got: {error!r}"
        )
        assert "slice-" in error, (
            f"the emitted error must state the expected slice-NN form -- got: {error!r}"
        )
        assert "carries no Slice-Id:/Step-Id: trailer" not in error, (
            "BUG: a commit that DOES carry a Slice-Id: trailer (bad value) "
            "must never collapse into the absent-trailer message -- "
            f"got: {error!r}"
        )

    def test_absent_trailer_never_claims_bad_value(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """NEGATIVE AT (`_never_`): a commit with genuinely NO
        Slice-Id/Step-Id trailer line must STILL get the "carries no
        trailer" message -- the fix must not overcorrect and make every
        empty parse claim a bad value. Pins the two-meanings-must-not-
        collapse property from the other direction.
        """
        repo = tmp_path / "repo"
        _init_repo_with_commit(repo, "do the thing with no trailer at all")

        trailers = _run_git(
            repo, "log", "-1", "--pretty=%(trailers:key=Slice-Id,valueonly)"
        )
        assert trailers.strip() == "", (
            "fixture setup broken: git sees a Slice-Id: trailer when none "
            f"was written -- got {trailers!r}"
        )

        exit_code = main(["--repo", str(repo), "--commit", "HEAD"])

        assert exit_code == 2, "malformed-input exit code expected (2)"
        event = _last_json_event(capsys)
        error = str(event.get("error", ""))
        assert "carries no Slice-Id:/Step-Id: trailer" in error, (
            "a commit with NO trailer line at all must still get the "
            f"absent-trailer message -- got: {error!r}"
        )

    def test_valid_slice_id_trailer_resolves_without_malformed_input(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Happy-path regression guard: a well-formed `Slice-Id: slice-01`
        trailer must resolve normally -- the fix must not regress this path.
        """
        repo = tmp_path / "repo"
        _init_repo_with_commit(repo, "do the thing\n\nSlice-Id: slice-01")

        exit_code = main(["--repo", str(repo), "--commit", "HEAD"])

        event = _last_json_event(capsys)
        assert event.get("event") != "MalformedInput", (
            f"a valid slice-01 trailer must not raise MalformedInput -- got: {event!r}"
        )
        # No .feature files exist in this throwaway repo, so E1 completeness
        # will report SliceCommitIncomplete (exit 1) -- NOT malformed input
        # (exit 2). The regression this test guards is trailer resolution
        # only; the completeness leg is out of scope here.
        assert exit_code != 2, (
            "valid trailer must not hit the malformed-input exit code -- "
            f"got exit {exit_code}, event {event!r}"
        )
