"""Regression: `des verify-slice-commit` WITHOUT `--feature-id` (an OPTIONAL
flag) emits `SliceCommitComplete` -- a PASS -- instead of INDETERMINATE (the
silent-false-green class #126).

RCA (verified LIVE by a sister nWave instance, confirmed here empirically
against current code): on a bare git repo (one committed file, no `.nwave`,
no ledger, zero `.feature` files anywhere) `des verify-slice-commit --repo
<r> --commit HEAD` WITHOUT `--feature-id` prints
``{"event": "SliceCommitComplete", ...}`` and exits 0. WITH `--feature-id` the
SAME repo/commit correctly reaches `SliceCommitRefused` (the E2 contract gate
has nothing to resolve). Cause: without `--feature-id`,
``_run_legacy_completeness`` (``src/des/cli/verify_slice_commit_completeness.py``)
computes E1 completeness via
``des.application.slice_at_completeness.missing_at_files`` ->
``feature_files_for_slice``, which -- with zero `.feature` files matching the
slice tag anywhere on the tree -- returns an EMPTY candidate list. An empty
candidate list yields an empty "missing" list (nothing to be missing FROM),
so ``_run_legacy_completeness`` (verify_slice_commit_completeness.py:753-776)
unconditionally emits ``SliceCommitComplete`` on ``deficient == {}`` --
"I verified everything" and "I had nothing to verify" collapse into the SAME
green output. This is the false-green a prior EXAMINE run hit (the examiner
had omitted `--feature-id`).

The fix (crafter's job, NOT this test's): when `--feature-id` is absent (or
present but no feature is resolvable), emit `SliceCommitIndeterminate` +
the dedicated INDETERMINATE exit code
(``verify_slice_commit_completeness._GATE_INDETERMINATE_EXIT_CODE``, 3) --
"you didn't tell me which feature to verify, so I verified NOTHING" -- never
a fabricated `SliceCommitComplete`. The E2/feature-scoped verification logic
(``_run_verify_then_record``) is untouched by this bug and by this test --
it already reaches its real verdict (confirmed by
``test_present_feature_id_is_never_downgraded_to_indeterminate`` below).

Driving surface: ``des.cli.verify_slice_commit_completeness.main(argv)``, the
CLI's real entry point (in-process, composition-root driving port), against a
REAL throwaway git repo built under ``tmp_path`` (real `git init`/`add`/
`commit`; LOCAL `git config user.email`/`user.name`, never `--global`). The
observable is the emitted JSON verdict + exit code -- never internals.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli.verify_slice_commit_completeness import (
    _GATE_INDETERMINATE_EXIT_CODE,
    main,
)


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_bare_slice_repo(repo: Path, *, slice_id: str = "slice-01") -> None:
    """Build a real, throwaway git repo carrying ONE commit with a valid
    `Slice-Id:` trailer -- and NOTHING else: no `.feature` files, no
    `.nwave/`, no ledger. The minimal fixture that reproduces the RCA:
    "verified nothing" and "verified everything" must not collapse.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", f"do the thing\n\nSlice-Id: {slice_id}")


def _last_json_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    """Parse the LAST single-line JSON event `main()` printed on stdout.

    ``main()`` may also print a one-off runtime-freshness notice ahead of the
    real verdict (``des.runtime.freshness.autoskipped``) -- the verdict is
    always the LAST JSON line on stdout, mirroring the established pattern in
    ``test_verify_slice_commit_trailer_value_message.py``.
    """
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines, f"expected at least one JSON line on stdout, got: {captured.out!r}"
    return json.loads(lines[-1])


class TestVerifySliceCommitRequiresFeatureId:
    """RED-CONFIRMED regression: a missing `--feature-id` must never emit a
    `SliceCommitComplete` PASS -- it verified nothing, so it must say so.
    """

    def test_missing_feature_id_is_indeterminate_not_complete(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """POSITIVE (the bug, RED today): a bare repo with zero `.feature`
        files anywhere and NO `--feature-id` must emit
        `SliceCommitIndeterminate` (exit
        `_GATE_INDETERMINATE_EXIT_CODE` == 3) -- NEVER the false-green
        `SliceCommitComplete` (exit 0) that today's code emits, because E1
        completeness vacuously reports "nothing missing" when it found ZERO
        `.feature` candidates to check in the first place.
        """
        repo = tmp_path / "repo"
        _init_bare_slice_repo(repo)

        # Confirm the fixture is honest: no `.feature` AT file exists
        # anywhere on this throwaway tree -- the gate has literally nothing
        # to verify E1 completeness against.
        assert not list(repo.rglob("*.feature")), (
            "fixture setup broken: a .feature file exists on the throwaway "
            "tree -- this test requires a repo with ZERO .feature files"
        )

        exit_code = main(["--repo", str(repo), "--commit", "HEAD"])

        event = _last_json_event(capsys)
        assert event.get("event") != "SliceCommitComplete", (
            "BUG: a slice commit verified with NO --feature-id must never "
            f"emit the false-green SliceCommitComplete -- got: {event!r}"
        )
        assert event.get("event") == "SliceCommitIndeterminate", (
            "a missing --feature-id must produce an honest "
            f"SliceCommitIndeterminate verdict -- got: {event!r}"
        )
        assert exit_code == _GATE_INDETERMINATE_EXIT_CODE, (
            "a missing --feature-id must exit with the dedicated "
            f"INDETERMINATE exit code ({_GATE_INDETERMINATE_EXIT_CODE}) -- "
            f"got exit {exit_code}, event {event!r}"
        )
        error = str(event.get("error", "")).lower()
        assert "feature" in error, (
            "the emitted reason must explain that no feature was specified "
            f"or resolvable to verify against -- got: {event.get('error')!r}"
        )

    def test_present_feature_id_is_never_downgraded_to_indeterminate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """NEGATIVE AT (`_never_`): the fix must NOT overcorrect. The SAME
        bare repo/commit, but WITH `--feature-id` supplied, must still reach
        its REAL verdict (here: `SliceCommitRefused` -- E2's contract gate
        has nothing to resolve for a non-existent feature) -- it must NOT be
        forced into the missing-feature-id `SliceCommitIndeterminate` path.
        Pins that only the MISSING-`--feature-id` case changes: the two
        absences (no --feature-id at all vs. a --feature-id that legitimately
        can't verify) stay distinguishable.
        """
        repo = tmp_path / "repo"
        _init_bare_slice_repo(repo)

        exit_code = main(
            [
                "--repo",
                str(repo),
                "--commit",
                "HEAD",
                "--feature-id",
                "some-nonexistent-feature",
            ]
        )

        event = _last_json_event(capsys)
        assert event.get("event") == "SliceCommitRefused", (
            "a present --feature-id must reach its OWN real verdict "
            f"(SliceCommitRefused via E2) -- got: {event!r}"
        )
        assert event.get("refused_half") == "E2", (
            "the refusal must come from E2 (the contract gate resolving "
            f"nothing for the feature) -- got: {event!r}"
        )
        assert exit_code == 1, (
            f"a present --feature-id refusal must exit 1 -- got {exit_code}"
        )
        # The distinguishing property: this must NOT be the missing-
        # feature-id INDETERMINATE outcome.
        assert event.get("event") != "SliceCommitIndeterminate", (
            "BUG-OVERCORRECTION: a present --feature-id must never be "
            f"downgraded to the missing-feature-id INDETERMINATE path -- "
            f"got: {event!r}"
        )
        assert exit_code != _GATE_INDETERMINATE_EXIT_CODE

    def test_missing_feature_id_indeterminate_distinct_from_malformed_input(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Boundary regression guard: the NEW missing-`--feature-id`
        INDETERMINATE exit code must stay distinct from the PRE-EXISTING
        malformed-input exit code (2, e.g. no `Slice-Id:` trailer at all) --
        the fix must add a third distinguishable outcome, not collapse two
        already-different meanings ("no trailer" vs "no feature to verify
        against") into the same exit code.
        """
        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        _run_git(repo, "init", "-q")
        _run_git(repo, "config", "user.email", "test@example.com")
        _run_git(repo, "config", "user.name", "Test")
        (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
        _run_git(repo, "add", "README.md")
        _run_git(repo, "commit", "-q", "-m", "no trailer at all here")

        malformed_exit = main(["--repo", str(repo), "--commit", "HEAD"])
        malformed_event = _last_json_event(capsys)
        assert malformed_event.get("event") == "MalformedInput"
        assert malformed_exit == 2

        repo2 = tmp_path / "repo2"
        _init_bare_slice_repo(repo2)
        indeterminate_exit = main(["--repo", str(repo2), "--commit", "HEAD"])
        indeterminate_event = _last_json_event(capsys)

        assert indeterminate_exit != malformed_exit, (
            "the missing-feature-id INDETERMINATE exit code must be "
            f"distinct from the malformed-input exit code ({malformed_exit}) "
            f"-- got the same code for both: {indeterminate_event!r}"
        )
        assert indeterminate_event.get("event") != "MalformedInput"
