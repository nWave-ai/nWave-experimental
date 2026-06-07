"""Unit tests for the reverify-slice-commit CLI scaffold (step 01-01).

Scope of step 01-01 is ONLY the scaffold: argument parsing and the
MalformedInput path. Preconditions and gate composition are steps 02-07
and are NOT exercised here.

Exit vocabulary: 0 success, 1 refused/blocked, 2 malformed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.reverify_slice_commit import _build_parser, main


# --- Criterion 1: required args are parsed -----------------------------------


def test_parser_accepts_all_four_required_args() -> None:
    """The four required args parse into the expected namespace."""
    args = _build_parser().parse_args(
        [
            "--repo",
            "/some/repo",
            "--feature-id",
            "fix-carpaccio-reverify-orphaned-slice",
            "--slice-id",
            "slice-03",
            "--commit",
            "HEAD",
        ]
    )

    assert args.repo == "/some/repo"
    assert args.feature_id == "fix-carpaccio-reverify-orphaned-slice"
    assert args.slice_id == "slice-03"
    assert args.commit == "HEAD"


@pytest.mark.parametrize(
    "missing_flag",
    ["--repo", "--feature-id", "--slice-id", "--commit"],
)
def test_parser_rejects_a_missing_required_arg(missing_flag: str) -> None:
    """Omitting any one of the four required args is an argparse usage error."""
    full = {
        "--repo": "/some/repo",
        "--feature-id": "fix-carpaccio-reverify-orphaned-slice",
        "--slice-id": "slice-03",
        "--commit": "HEAD",
    }
    argv: list[str] = []
    for flag, value in full.items():
        if flag == missing_flag:
            continue
        argv.extend([flag, value])

    with pytest.raises(SystemExit) as excinfo:
        _build_parser().parse_args(argv)

    assert excinfo.value.code == 2


# --- Criterion 2: malformed --slice-id ---------------------------------------


@pytest.mark.parametrize(
    "bad_slice_id",
    ["slice-", "slice", "sliceNN", "03", "slice_03", "", "Slice-03"],
)
def test_malformed_slice_id_emits_malformed_input_and_exits_2(
    bad_slice_id: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A --slice-id not matching slice-NN is MalformedInput, exit 2."""
    exit_code = main(
        [
            "--repo",
            str(tmp_path),
            "--feature-id",
            "fix-carpaccio-reverify-orphaned-slice",
            "--slice-id",
            bad_slice_id,
            "--commit",
            "HEAD",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "MalformedInput"
    assert "slice-id" in payload["error"]


# slice-3a / slice-12b: letter-suffix carpaccio sub-slices are VALID per the
# eb8915e04 regex relax (friction #10, _SLICE_ID_RE = ^slice-\d+(?:[a-z])?$).
# slice-3a was previously (incorrectly) listed as malformed — stale test drift
# from that intentional relax; corrected 2026-05-28.
@pytest.mark.parametrize(
    "good_slice_id", ["slice-1", "slice-03", "slice-12", "slice-3a", "slice-12b"]
)
def test_well_formed_slice_id_does_not_trip_the_slice_id_check(
    good_slice_id: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A well-formed slice-id passes the format check.

    With a valid repo but an unreadable commit the run still ends as
    MalformedInput (criterion 3), but the error must NOT be the slice-id
    error -- proving slice-NN was accepted.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    exit_code = main(
        [
            "--repo",
            str(tmp_path),
            "--feature-id",
            "fix-carpaccio-reverify-orphaned-slice",
            "--slice-id",
            good_slice_id,
            "--commit",
            "does-not-exist",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "MalformedInput"
    assert "slice-id" not in payload["error"]


# --- Criterion 3: unreadable repo or commit ----------------------------------


def test_unreadable_repo_emits_malformed_input_and_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A path that is not a git repository is MalformedInput, exit 2."""
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()

    exit_code = main(
        [
            "--repo",
            str(non_repo),
            "--feature-id",
            "fix-carpaccio-reverify-orphaned-slice",
            "--slice-id",
            "slice-03",
            "--commit",
            "HEAD",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "MalformedInput"
    assert payload["error"]


def test_unreadable_commit_emits_malformed_input_and_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A commit-ish that cannot be resolved is MalformedInput, exit 2."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    exit_code = main(
        [
            "--repo",
            str(tmp_path),
            "--feature-id",
            "fix-carpaccio-reverify-orphaned-slice",
            "--slice-id",
            "slice-03",
            "--commit",
            "deadbeefdeadbeef",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "MalformedInput"
    assert payload["error"]


# --- Preconditions P1/P2/P3 helpers ------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


def _init_repo(repo: Path) -> None:
    """Initialise a git repo with deterministic identity."""
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def _commit(repo: Path, message: str, filename: str = "f.txt") -> str:
    """Create a file, commit it with ``message``, return the commit SHA."""
    (repo / filename).write_text(filename, encoding="utf-8")
    subprocess.run(["git", "add", filename], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
    return _git(repo, "rev-parse", "HEAD").strip()


def _argv(repo: Path, slice_id: str, commit: str) -> list[str]:
    return [
        "--repo",
        str(repo),
        "--feature-id",
        "fix-carpaccio-reverify-orphaned-slice",
        "--slice-id",
        slice_id,
        "--commit",
        commit,
    ]


# --- Criterion 1: P1 ancestor check ------------------------------------------


def test_p1_non_ancestor_commit_is_refused_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A commit not an ancestor of HEAD is SliceReverifyRefused, exit 1."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _commit(repo, "Slice-Id: slice-01\n", filename="base.txt")
    # A commit on a divergent branch -- not an ancestor of HEAD.
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    side_sha = _commit(repo, "Slice-Id: slice-02\n", filename="side.txt")
    subprocess.run(
        ["git", "checkout", "-q", "-"], cwd=repo, check=True
    )  # back to default branch
    _commit(repo, "Slice-Id: slice-03\n", filename="more.txt")

    exit_code = main(_argv(repo, "slice-02", side_sha))

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "SliceReverifyRefused"
    assert "ancestor" in payload["error"].lower()


# --- Criterion 2: P2 slice-id trailer membership -----------------------------


def test_p2_commit_without_slice_id_in_trailer_set_is_refused_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A --slice-id absent from the commit's trailer set is refused, exit 1."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    buried = _commit(repo, "feat: thing\n\nSlice-Id: slice-01\n", filename="a.txt")
    _commit(repo, "feat: later\n\nSlice-Id: slice-09\n", filename="b.txt")

    # buried carries slice-01; ask to reverify slice-07 -- not a member.
    exit_code = main(_argv(repo, "slice-07", buried))

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "SliceReverifyRefused"
    assert "slice-07" in payload["error"]


def test_p2_accepts_slice_id_member_of_a_multi_trailer_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A --slice-id that IS a member of a multi-Slice-Id commit passes P2.

    Step 01-05 NOTE: P4 (in-commit AT presence) lands a new precondition
    after P3 that ALSO emits `SliceReverifyRefused` when the bare commit
    carries no `@slice-02` `.feature`. The original proxy assertion -- "no
    `SliceReverifyRefused` event emitted" => "P2 did not refuse" -- is no
    longer valid: a P4 refusal is also a `SliceReverifyRefused`. The genuine
    P2 contract this test guards is "the run was NOT refused on a P2
    trailer-membership ground", which is asserted directly by checking the
    refusal error does not carry P2's "is not in the commit's trailer set"
    phrasing. slice-02 IS a trailer member, so P2 accepts it; the run then
    refuses downstream (P4: the bare commit ships no `@slice-02` `.feature`).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    buried = _commit(
        repo,
        "feat: batched\n\nSlice-Id: slice-01\nSlice-Id: slice-02\n",
        filename="a.txt",
    )
    _commit(repo, "feat: later\n\nSlice-Id: slice-03\n", filename="b.txt")

    exit_code = main(_argv(repo, "slice-02", buried))

    # P2 passed: the run was not refused on a trailer-membership ground.
    out = capsys.readouterr().out.strip()
    assert exit_code != 0  # refused downstream of P2 (P4: no @slice-02 .feature)
    payload = json.loads(out)
    assert "is not in the commit's trailer set" not in payload.get("error", "")


# --- Criterion 3: P3 not-already-verified ------------------------------------


def _write_verified_ledger(repo: Path, feature_id: str, slice_id: str) -> None:
    """Append a genuine SliceCommitVerified ledger record for ``slice_id``."""
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    ledger = AtCompletionLedger(feature_id, repo)
    ledger.append_gate_event("SliceCommitVerified", slice_id)


def test_p3_already_verified_slice_is_refused_idempotently_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An already-verified slice is refused idempotently, exit 1, no ledger write."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    buried = _commit(repo, "feat: thing\n\nSlice-Id: slice-01\n", filename="a.txt")
    _commit(repo, "feat: later\n\nSlice-Id: slice-02\n", filename="b.txt")

    feature_id = "fix-carpaccio-reverify-orphaned-slice"
    _write_verified_ledger(repo, feature_id, "slice-01")

    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    ledger = AtCompletionLedger(feature_id, repo)
    records_before = len(ledger.read_records())

    exit_code = main(_argv(repo, "slice-01", buried))

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "SliceReverifyRefused"
    assert "slice-01" in payload["error"]
    assert "verif" in payload["error"].lower()
    # No ledger record was appended by the refusal.
    assert len(ledger.read_records()) == records_before


def test_p3_corrupt_ledger_is_surfaced_as_structured_non_zero_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A LedgerIntegrityViolation from read is surfaced, never proceeds onto it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    buried = _commit(repo, "feat: thing\n\nSlice-Id: slice-01\n", filename="a.txt")
    _commit(repo, "feat: later\n\nSlice-Id: slice-02\n", filename="b.txt")

    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    feature_id = "fix-carpaccio-reverify-orphaned-slice"
    ledger = AtCompletionLedger(feature_id, repo)
    ledger.append_gate_event("SliceCommitVerified", "slice-01")
    # Corrupt the chain: a non-JSON line trips the M7 fail-closed read.
    path = ledger.ledger_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write("this-is-not-json\n")

    exit_code = main(_argv(repo, "slice-01", buried))

    assert exit_code != 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "LedgerIntegrityViolation"
    assert payload["error"]


def test_module_is_runnable_as_python_m(tmp_path: Path) -> None:
    """`python -m des.cli.reverify_slice_commit` is a valid entry point."""
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.cli.reverify_slice_commit",
            "--repo",
            str(non_repo),
            "--feature-id",
            "fix-carpaccio-reverify-orphaned-slice",
            "--slice-id",
            "slice-03",
            "--commit",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[4],
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout.strip())
    assert payload["event"] == "MalformedInput"
