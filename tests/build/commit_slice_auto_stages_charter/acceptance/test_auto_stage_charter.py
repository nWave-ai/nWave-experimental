"""Acceptance: `des commit-slice` auto-stages the feature's expectation charter.

Feature: commit-slice-auto-stages-charter
(docs/feature/commit-slice-auto-stages-charter/feature-delta.md)

VALUE: `des commit-slice` already stages the AT + the feature-delta for a
slice seal, but the EXPECTATION CHARTER (docs/product/expectations/{feature-id}/)
is only committed if the operator remembers to pass it via --path. Root cause:
operator-remembered staging (GDP-5 violation -- the cost is on the operator).
FIX: the staged-path assembly in commit_slice.py ALWAYS includes
docs/product/expectations/{feature-id}/ (if it exists on disk) alongside the
explicit --path entries -- the same first-class treatment the AT + the
feature-delta already get, so a slice/feature can never seal leaving its
EXAMINE charter behind.

DRIVING PORT: `des.cli.commit_slice.main` (the real `des commit-slice` CLI
entry point / composition root) over a REAL disposable git repo -- no mock of
git. Real `git` subprocesses underneath (Mandate 6/16 -- driving-port-only
boundary). Outcome is asserted by reading the REAL committed tree via
`git show --name-only HEAD`, never a staged-path list a mock returned.

PINNED SEAM (production code, NOT YET IMPLEMENTED -- these ATs drive only the
EXISTING `main()` entry point and never import a not-yet-existing symbol, so
they are active-RED, never BROKEN):

    def _charter_dir_to_stage(repo: Path, feature_id: str | None) -> list[str]:
        '''Repo-relative `docs/product/expectations/{feature_id}/` if it
        exists on disk, else `[]`. Feature-scoped only -- never the whole
        expectations tree.'''

    ...folded into `main()` immediately before the `_stage(repo, args.paths,
    args.all)` call (line ~915 today), e.g. `args.paths = [*args.paths,
    *_charter_dir_to_stage(repo, args.feature_id)]` when not `args.all`.
    `git add` is idempotent, so an operator-supplied `--path` to the same dir
    causes no double-add error.

Examine-verdict gate note: a charter file matching `*.md` under
docs/product/expectations/{feature_id}/ ARMS the pre-existing commit-time
examine gate (`check_examine_verdict` -- an UNRELATED feature). AT-1/AT-3/AT-4
record a PASS ExamineVerdict for the entering slice first (mirrors
tests/des/integration/test_commit_slice_examine_gate.py), isolating this AT
set to the auto-stage contract only -- never coupled to the examine gate's own
pass/fail semantics.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.charter_fixtures import filled_charter

from des.cli.commit_slice import main as commit_slice_main
from des.cli.record_examine_verdict import main as record_examine_verdict_main


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_repo(root: Path) -> None:
    """Init a git work-tree with one committed base file (the slice's parent)."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def _committed_files(repo: Path) -> set[str]:
    """The repo-relative file set CURRENT HEAD's tree carries (real git read)."""
    out = _git(repo, "show", "--name-only", "--format=", "HEAD")
    return {line for line in out.splitlines() if line.strip()}


def _write_charter(repo: Path, feature_id: str, name: str, body: str) -> str:
    """Write a charter under the User-Examiner convention; return its repo-relative path."""
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_file = charter_dir / name
    charter_file.write_text(body, encoding="utf-8")
    return str(charter_file.relative_to(repo))


def _record_pass_verdict(
    repo: Path, feature_id: str, slice_id: str, charter_relpath: str, capsys
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
            "PASS",
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


def test_charter_present_but_not_dashdash_path_is_auto_staged_into_commit(
    tmp_path: Path, capsys
) -> None:
    """POSITIVE (RED today): a present charter, NOT passed via --path, IS committed.

    Today `_stage()` only stages `--path`/`--all` entries; the charter dir is
    never appended -- this fails semantically (the committed file set omits
    the charter) until the auto-stage fix lands.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-charter-owner", "slice-01"
    charter_relpath = _write_charter(
        repo, feature_id, "some-charter.md", filled_charter("Walk the checkout flow.")
    )
    _record_pass_verdict(repo, feature_id, slice_id, charter_relpath, capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--path",
            "tests/unit/test_slice_01.py",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    committed = _committed_files(repo)
    assert charter_relpath in committed, (
        f"expected the charter {charter_relpath!r} to be auto-staged into the "
        f"commit; committed files were {sorted(committed)}"
    )


def test_absent_charter_dir_seals_with_no_error(tmp_path: Path, capsys) -> None:
    """NEGATIVE / absent: no expectations dir for the feature -> no crash, normal seal.

    Absence is legitimate, not a failure -- e.g. an @infrastructure slice with
    no observable charter never blocks on a missing auto-stage target.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-no-charter-at-all", "slice-01"
    # No docs/product/expectations/{feature_id}/ directory is ever created.

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--path",
            "tests/unit/test_slice_01.py",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_01.py",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    committed = _committed_files(repo)
    assert not any("docs/product/expectations" in path for path in committed)


def test_explicit_dashdash_path_charter_is_idempotent_with_auto_stage(
    tmp_path: Path, capsys
) -> None:
    """IDEMPOTENT: explicit --path to the charter dir + auto-stage -> committed once.

    An operator who ALSO passes --path docs/product/expectations/{id}/ gets
    the SAME result as auto-stage alone -- no double-add error, no duplicate
    entry in the committed file set.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-charter-explicit-path", "slice-01"
    charter_relpath = _write_charter(
        repo, feature_id, "some-charter.md", filled_charter("Walk the checkout flow.")
    )
    _record_pass_verdict(repo, feature_id, slice_id, charter_relpath, capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    charter_dir_relpath = str(Path(charter_relpath).parent)
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--path",
            "tests/unit/test_slice_01.py",
            "--path",
            charter_dir_relpath,
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    committed = _committed_files(repo)
    matches = [path for path in committed if path == charter_relpath]
    assert matches == [charter_relpath], (
        f"expected the charter committed EXACTLY ONCE; committed files were "
        f"{sorted(committed)}"
    )


def test_auto_stage_scoped_to_owning_feature_only(tmp_path: Path, capsys) -> None:
    """SCOPE guard: only F's charter dir is staged -- a sibling feature's is not.

    A DIFFERENT feature's docs/product/expectations/{other}/ present in the
    tree is NOT staged by F's seal -- auto-staging is feature-scoped, never
    the whole expectations tree (mirrors how the AT + feature-delta are
    already feature-scoped).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id, slice_id = "f-charter-owner-scope", "slice-01"
    other_feature_id = "f-charter-sibling-scope"
    charter_relpath = _write_charter(
        repo, feature_id, "some-charter.md", filled_charter("Walk the checkout flow.")
    )
    other_charter_relpath = _write_charter(
        repo,
        other_feature_id,
        "other-charter.md",
        filled_charter("A sibling feature."),
    )
    _record_pass_verdict(repo, feature_id, slice_id, charter_relpath, capsys)

    _add_new_slice_file(repo, "test_slice_01.py")
    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--path",
            "tests/unit/test_slice_01.py",
            "--feature-id",
            feature_id,
            "--message",
            f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    committed = _committed_files(repo)
    assert charter_relpath in committed
    assert other_charter_relpath not in committed
