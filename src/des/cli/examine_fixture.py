"""des examine-fixture -- the producing tool for an examiner-drivable
certification-gate fixture (examinable-gate-surface feature, slice-01).

nWave's independent examiner cannot read source code -- that blindness is her
entire value: an oracle derived from the subject always returns a perfect
image. But the certification gates (`des verify-slice-commit`, `des
commit-slice`) can only be driven against a repository with a real Slice
Plan, real `Slice-Id:`-trailered commits, a real `SliceCommitVerified`
ledger record, and regression-test files named by a convention that lives
only in the gate's own implementation. Measured 2026-07-13: an examiner
dispatched against a certification-gate fix could not reach it and rationally
defected to running the producer's own test suite -- a mirror, VOID verdict.
Then the orchestrator, WITH full source access, hand-built a fixture and the
real gate STILL refused the clean case, because the naming convention had to
be reverse-engineered from the source.

This command hands an examiner that world in ONE call: a real git repo whose
slice-01 is genuinely SHIPPED (a real `Slice-Id:`-trailered commit AND a real
`SliceCommitVerified` ledger record written through
`AtCompletionLedger.append_gate_event`), whose slice-02 is the entering
slice, and whose slice-03 is a deliberately-red work-ahead test -- every
slice's regression test flippable red/green by editing a single `assert`
line. The printed JSON payload names everything an examiner needs to drive
and perturb the world without ever opening this tool's or the gate's source.

Arch invariant (feature-delta.md): every regression-file name below is
DERIVED from the gate's own naming-convention resolver
(`des.cli.verify_slice_commit_completeness.canonical_regression_test_path`,
itself widened from the gate's private `_regression_file_glob_candidates`
seam) -- never re-declared here. The shipped slice's attestation goes through
the REAL ledger writer (`AtCompletionLedger`) -- never hand-written JSONL.

Git write-capable helper (`_git`/`_git_init`/`_commit_with_trailer`) is the
one CREATE_NEW component the feature-delta Reuse Analysis authorises: the
proven throwaway-repo git shape already used by
`tests/bugs/des/test_contract_gate_scopes_shipped_plus_entering.py`,
re-expressed here in production code (a production tool cannot import from
`tests/`). Own local `user.name`/`user.email` per repo (git-safety rule #48)
-- never touches the real project's git config.

CLI contract:
    des examine-fixture --out <dir> [--feature-id <id>]

stdout token (JSON, one line): {repo, feature_id, shipped_slice,
entering_slice, work_ahead_slice, flip_instructions}. Each slice entry
carries {slice_id, test_file, currently_passing}. Exits 0 unconditionally --
this is a producing tool, not a gate (the gate it feeds is `des
verify-slice-commit`).
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.verify_slice_commit_completeness import canonical_regression_test_path


_SHIPPED_SLICE = "slice-01"
_ENTERING_SLICE = "slice-02"
_WORK_AHEAD_SLICE = "slice-03"
_DEFAULT_FEATURE_ID = "examine-fixture-demo"


def _flip_instructions(repo: Path, feature_id: str) -> str:
    """Human-readable explanation of the flip lever, carrying a LITERAL,
    copy-pasteable gate command -- never a `<repo>`/`<feature_id>`
    placeholder.

    The tool already knows both values at print time (they are printed two
    fields above, in the same JSON) -- making the examiner re-substitute
    them is charging her for work the tool already did (GDP-5), and the
    most plausible wrong substitution (`<repo>` -> `.`) silently aims the
    certification gate at her own working repository instead of the
    fixture (the recurrence this fixes, 2026-07-13).
    """
    command = (
        f"des verify-slice-commit --repo {shlex.quote(str(repo))} "
        f"--commit HEAD --feature-id {shlex.quote(feature_id)}"
    )
    return (
        "each slice's regression test is a single `assert True` (green) or "
        "`assert False` (red) line -- flip a slice red or green by editing "
        f"that one line in its test_file, then re-run `{command}` to see "
        "the real gate's verdict."
    )


def _git(repo: Path, *args: str) -> str:
    """Write-capable git call scoped to ``repo`` (returns stdout, raises on
    non-zero). Never touches the real project's git config (rule #48) --
    every invocation is explicit-target (``git -C <repo> ...``), never a
    bare ``git config``.
    """
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _git_init(repo: Path) -> None:
    """An isolated repo with its OWN local git identity -- never the real
    project repo's ``user.name``/``user.email``."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "examine-fixture@nwave.invalid")
    _git(repo, "config", "user.name", "examine-fixture")


def _commit_with_trailer(
    repo: Path, slice_id: str, subject: str, *, allow_empty: bool = False
) -> None:
    """Stage everything and commit with a real ``Slice-Id:`` trailer -- the
    SAME trailer shape ``des verify-slice-commit`` reads off HEAD.
    """
    _git(repo, "add", "-A")
    args = ["commit", "-q"]
    if allow_empty:
        args.append("--allow-empty")
    args += ["-m", f"{subject}\n\nSlice-Id: {slice_id}"]
    _git(repo, *args)


def _regression_test_body(slice_id: str, *, passing: bool) -> str:
    """A real, pytest-collectible regression test whose ENTIRE verdict is
    one `assert True` (green) or `assert False` (red) line -- the flip lever
    an examiner edits to break an already-delivered slice on purpose.
    """
    slice_us = slice_id.replace("-", "_")
    verdict = "assert True" if passing else "assert False"
    return (
        f'"""Regression test for {slice_id} of the examine-fixture repo.\n\n'
        "Flip this slice red or green by editing the single `assert` line "
        "below -- that is the lever an examiner uses to break an "
        "already-delivered slice on purpose, without ever reading this "
        "tool's or the certification gate's own source.\n"
        '"""\n\n\n'
        f"def test_{slice_us}_behaviour() -> None:\n"
        f"    {verdict}\n"
    )


def _write_regression_test(
    repo: Path, feature_id: str, slice_id: str, *, passing: bool
) -> Path:
    """Write ``slice_id``'s regression test at the path the gate's OWN
    naming-convention resolver derives (``canonical_regression_test_path`` --
    widened from the gate's private ``_regression_file_glob_candidates``
    seam, never re-declared here per the feature's arch invariant).
    """
    relative = canonical_regression_test_path(feature_id, slice_id)
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_regression_test_body(slice_id, passing=passing), encoding="utf-8")
    return path


def _write_feature_delta(repo: Path, feature_id: str) -> None:
    feature_dir = repo / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature-delta.md").write_text(
        f"# {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {_SHIPPED_SLICE} | the first delivered behaviour | shipped | | "
        "examine-fixture slice |\n"
        f"| {_ENTERING_SLICE} | the behaviour being delivered now | pending "
        "| | examine-fixture slice |\n"
        f"| {_WORK_AHEAD_SLICE} | a behaviour nobody has built yet | "
        "pending | | examine-fixture slice, deliberately unimplemented |\n",
        encoding="utf-8",
    )


def _write_repo_scaffolding(repo: Path, feature_id: str) -> None:
    """The minimal on-disk shape ``des verify-slice-commit`` expects to find
    a project at all -- a `pyproject.toml`, an `atdd_pure` `.nwave/config.yaml`,
    and the feature's `feature-delta.md`."""
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "{feature_id}"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    nwave_dir = repo / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    (nwave_dir / "config.yaml").write_text(
        "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
    )
    _write_feature_delta(repo, feature_id)


def _slice_payload(
    repo: Path, slice_id: str, test_path: Path, *, passing: bool
) -> dict[str, object]:
    return {
        "slice_id": slice_id,
        "test_file": str(test_path.relative_to(repo)),
        "currently_passing": passing,
    }


def build_fixture(
    out_dir: Path, feature_id: str = _DEFAULT_FEATURE_ID
) -> dict[str, object]:
    """Build the examinable fixture repo at ``out_dir``. Not pure (filesystem
    + git + the real ledger writer). Returns the printable payload.

    Sequence: init a repo -> write slice-01's (green) and slice-03's (red)
    regression tests -> commit slice-01 (`Slice-Id: slice-01`) -> attest
    slice-01 as SHIPPED through the REAL ledger writer (never hand-written
    JSONL) -> write slice-02's (green) regression test -> commit slice-02
    (`Slice-Id: slice-02`, the entering slice, HEAD). slice-03's file is
    written but deliberately never wired into {shipped} union {entering} --
    it is a work-ahead test nobody has built yet.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
    _git_init(out_dir)
    _write_repo_scaffolding(out_dir, feature_id)

    shipped_test = _write_regression_test(
        out_dir, feature_id, _SHIPPED_SLICE, passing=True
    )
    work_ahead_test = _write_regression_test(
        out_dir, feature_id, _WORK_AHEAD_SLICE, passing=False
    )
    _commit_with_trailer(out_dir, _SHIPPED_SLICE, "feat(fixture): slice-01 delivered")

    # The shipped slice's attestation goes through the REAL ledger writer --
    # never hand-written JSONL bytes (feature-delta.md C3 / arch invariant).
    AtCompletionLedger(feature_id, out_dir).append_gate_event(
        event="SliceCommitVerified", slice_id=_SHIPPED_SLICE
    )

    entering_test = _write_regression_test(
        out_dir, feature_id, _ENTERING_SLICE, passing=True
    )
    _commit_with_trailer(out_dir, _ENTERING_SLICE, "feat(fixture): slice-02 entering")

    return {
        "repo": str(out_dir),
        "feature_id": feature_id,
        "shipped_slice": _slice_payload(
            out_dir, _SHIPPED_SLICE, shipped_test, passing=True
        ),
        "entering_slice": _slice_payload(
            out_dir, _ENTERING_SLICE, entering_test, passing=True
        ),
        "work_ahead_slice": _slice_payload(
            out_dir, _WORK_AHEAD_SLICE, work_ahead_test, passing=False
        ),
        "flip_instructions": _flip_instructions(out_dir, feature_id),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des examine-fixture",
        description=(
            "Build a real, drivable repository the REAL certification gate "
            "(`des verify-slice-commit`) accepts on the clean case -- a "
            "genuinely SHIPPED+attested slice, an entering slice, and a "
            "deliberately-red work-ahead slice, each flippable red or green "
            "by editing a single line -- so an examiner who cannot read "
            "source can still reach and break the gate's real surface."
        ),
    )
    parser.add_argument(
        "--out", required=True, help="Directory to build the fixture repo at."
    )
    parser.add_argument(
        "--feature-id",
        default=_DEFAULT_FEATURE_ID,
        help="Feature id the fixture repo is built under (default: %(default)s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Build the fixture and print its driving payload as one JSON line.
    Always exits 0 -- this is a producing tool, not a gate."""
    args = _build_parser().parse_args(argv)
    payload = build_fixture(Path(args.out), args.feature_id)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
