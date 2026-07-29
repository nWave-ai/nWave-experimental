"""Integration test: the commit-time examine-verdict gate (evolution-plan P1.2).

``des commit-slice`` mechanically requires a slice to have been EXAMINED (a
human-intent charter walked through the real surface by ``nw-user-examiner``,
verdict recorded via ``des record-examine-verdict``) before it may commit --
replacing the per-slice code-reading C_REVIEWER_AUDIT with execution-
observation. The gate is ARMED only when a charter exists for the feature
under ``docs/product/expectations/{feature_id}/*.md`` (or the operator opts in
via ``NWAVE_EXAMINE_GATE_OPT_IN=1``), so the pre-existing commit-slice test
suite (no charters, no opt-in) stays green -- see
``test_commit_slice_no_charter_leaves_gate_unarmed`` below for the explicit
backward-compat pin.

Real I/O: a real tmp git work-tree, real ``git`` subprocesses -- mirrors
``tests/des/integration/test_commit_slice.py``'s harness.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from des.cli.record_examine_verdict import main as record_examine_verdict_main
from tests.charter_fixtures import filled_charter
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


def _write_charter(repo: Path, feature_id: str, slice_id: str, body: str) -> str:
    """Write a charter under the User-Examiner convention; return its repo-relative path."""
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_file = charter_dir / f"{slice_id}.md"
    charter_file.write_text(body, encoding="utf-8")
    return str(charter_file.relative_to(repo))


def _record_examine_verdict(
    repo: Path,
    feature_id: str,
    slice_id: str,
    charter_relpath: str,
    verdict: str,
    capsys,
) -> None:
    exit_code = record_examine_verdict_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--slice",
            slice_id,
            "--charter",
            charter_relpath,
            "--verdict",
            verdict,
            "--observations",
            f"observed during {slice_id} walkthrough",
            "--examiner",
            "nw-user-examiner",
        ]
    )
    capsys.readouterr()  # drain -- the producer's own JSON is not under test here
    assert exit_code == 0


def _add_new_slice_file(repo: Path, name: str) -> None:
    (repo / "tests" / "unit" / name).write_text(
        "def test_slice():\n    assert True\n", encoding="utf-8"
    )


def test_commit_refused_when_examine_verdict_is_fail(tmp_path: Path, capsys) -> None:
    """NEGATIVE: a recorded FAIL examine-verdict refuses the commit exit 1."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, filled_charter("Walk the checkout flow.")
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "FAIL", capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 1
    assert event["event"] == "ExamineVerdictRefused"
    assert event["slice_id"] == slice_id
    assert "what" in event and "why" in event and "how" in event


def test_commit_refused_when_no_verdict_recorded(tmp_path: Path, capsys) -> None:
    """NEGATIVE: charter exists (gate ARMED) but NO verdict recorded -> exit 2."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    _write_charter(
        repo, feature_id, slice_id, filled_charter("Walk the checkout flow.")
    )
    # No des record-examine-verdict call at all.

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictMissing"
    assert event["slice_id"] == slice_id
    assert "record-examine-verdict" in event["how"]


def test_commit_refused_when_pass_verdict_charter_changed_after(
    tmp_path: Path, capsys
) -> None:
    """NEGATIVE: PASS recorded, then charter bytes CHANGE -> stale-seal void, refused."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, filled_charter("ORIGINAL body.")
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "PASS", capsys)

    # Mutate the charter AFTER the exam -- the recorded charter_seal is now stale.
    (repo / charter).write_text(filled_charter("TAMPERED body."), encoding="utf-8")

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictStale"
    assert event["slice_id"] == slice_id


def test_commit_proceeds_when_pass_verdict_seal_matches(tmp_path: Path, capsys) -> None:
    """POSITIVE: PASS verdict + matching seal -> commit proceeds to SliceCommitted."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, filled_charter("Walk the checkout flow.")
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "PASS", capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert event["verified"] is True


def test_verified_record_attests_via_examine_verdict_when_that_cleared_it(
    tmp_path: Path, capsys
) -> None:
    """ADR-DES-001 addendum Rule 2 (attribution): a ``SliceCommitVerified``
    ledger record earned via the examine-verdict carve-out must carry
    ``attested_via: "examine-verdict"`` -- never a bare, unattributed
    restatement of ``verified: true``. Distinct invariant from Rule 1's
    carve-out itself (pinned by ``test_commit_proceeds_when_pass_verdict_
    seal_matches`` above): that test only proves the commit PROCEEDS; this
    one proves the record HONESTLY NAMES the evidence source that cleared
    it -- a reader must be able to tell "pytest gates ran and passed" apart
    from "no executable gate existed; a human-observed examine PASS is the
    proof" without inferring it from absence.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine-attribution", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, filled_charter("Walk the checkout flow.")
    )
    _record_examine_verdict(repo, feature_id, slice_id, charter, "PASS", capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    capsys.readouterr()  # drain -- the ledger record is the authority here

    assert exit_code == 0, (
        "reproduction precondition: an examine-cleared, E2-vacuous slice "
        f"must commit -- exit_code={exit_code!r}"
    )

    verified_records = AtCompletionLedger(feature_id, repo).read_records(
        slice_id=slice_id, event_type="SliceCommitVerified"
    )
    assert verified_records, (
        "reproduction precondition: a SliceCommitVerified ledger record "
        "must exist for the examine-cleared slice"
    )
    assert verified_records[-1].get("attested_via") == "examine-verdict", (
        "a SliceCommitVerified record earned via the examine-verdict "
        "carve-out must honestly name its evidence source -- observed "
        f"record={verified_records[-1]!r}"
    )


def test_commit_refused_when_verdict_is_indeterminate(tmp_path: Path, capsys) -> None:
    """INDETERMINATE verdict refuses LOUD (exit 2) -- never a silent pass."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-examine", "slice-01"
    charter = _write_charter(
        repo, feature_id, slice_id, filled_charter("Walk the checkout flow.")
    )
    _record_examine_verdict(
        repo, feature_id, slice_id, charter, "INDETERMINATE", capsys
    )

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 2
    assert event["event"] == "ExamineVerdictIndeterminate"
    assert event["slice_id"] == slice_id


def test_commit_slice_no_charter_leaves_gate_unarmed(tmp_path: Path, capsys) -> None:
    """BACKWARD-COMPAT: no charter for the feature -> examine gate not armed.

    No docs/product/expectations/ directory, no NWAVE_EXAMINE_GATE_OPT_IN, no
    ExamineVerdict recorded -- the examine-verdict gate (P1.2) is genuinely
    unarmed here, and this test is scoped to THAT gate only.

    Post reorder+carve-out (fix-commit-slice-verify-before-commit slice-01),
    `des commit-slice` ALSO refuses a pre-flight with ZERO observed AT
    evidence (no resolvable `.feature` file, no `--at-kind
    pytest-regression`, no recorded examine PASS) -- an orthogonal,
    independently-armed leg (E2). This fixture supplies neither a `.feature`
    file nor `--at-kind pytest-regression` evidence, so it now correctly hits
    THAT refusal (`SliceCommitRefused`, E2) rather than silently committing
    unverified -- the old "commits + verifies unconditionally" assumption was
    the pre-flight-less lie this reorder fixed; it is no longer true, nor
    should it be.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-no-charter", "slice-01"

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 1, (
        f"expected the zero-evidence pre-flight to refuse this commit -- "
        f"exit_code={exit_code!r}, event={event!r}"
    )
    assert event["event"] == "SliceCommitRefused", event
    # fix-e1-examine-verdict-carveout: E1's own examine-verdict carve-out now
    # runs BEFORE E2's, so a zero-evidence slice (no .feature, no
    # pytest-regression at-kind, no examine verdict, no exempt lane) is
    # caught earlier and more honestly at E1 -- this is the fix's intended
    # effect, not a regression.
    assert event["refused_half"] == "E1", event
