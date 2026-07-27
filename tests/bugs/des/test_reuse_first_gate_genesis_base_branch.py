"""Regression (defects.md: reuse-first-gate-branch-topology-false-positive):
``check_reuse_first_design`` diffs unscoped ``master...HEAD`` by default. On
a LONG-LIVED branch (many prior, already-landed features' commits sitting
between the true ``master`` merge-base and this feature's own HEAD) that
unscoped diff counts every file EVER added on the branch since it diverged
from master -- not just the files THIS feature's own commits introduced.
Those foreign new-components are absent from THIS feature's own Reuse
Analysis table (they were justified by a DIFFERENT feature's table, already
merged), so the gate false-FAILs the architect over work that isn't theirs.

Fix: ``--base-branch`` now defaults to ``None`` and is resolved via
``_resolve_base_branch`` -- the feature-delta's OWN git-genesis parent (the
commit BEFORE ``docs/feature/<id>/feature-delta.md`` first entered history),
reusing the shared ``des.adapters.driven.git.git_subprocess`` SSOT
(``resolve_feature_genesis_base_ref`` / ``resolve_default_base_ref``, the
SAME module ``walking_skeleton_gate.py``/``dormant_seam_gate.py`` already
consult for base-ref resolution -- no second algorithm), falling back to the
repo's resolved trunk, then the literal ``"master"``, when genesis cannot be
resolved. An EXPLICIT ``--base-branch`` still always wins.

Driving surface: the REAL ``scripts.cli.check_reuse_first_design.main()`` CLI
entry point, in-process, over a genuine throwaway git work-tree built with
explicit ``git`` subprocess calls (GIT SAFETY -- never against the real repo).
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest


_CLI_MODULE = "scripts.cli.check_reuse_first_design"


def _git(cwd: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in fixture staging (exit "
            f"{completed.returncode}): {completed.stderr.strip()[:300]}"
        )


def _commit(repo: Path, relative_path: str, content: str, message: str) -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "regression@nwave.test")
    _git(root, "config", "user.name", "regression")
    _commit(root, "README.md", "seed\n", "chore: seed the fixture repo")
    return root


_FEATURE_ID = "reuse-first-genesis-probe"


def _write_feature_delta_justifying(repo: Path, component_name: str) -> None:
    delta_dir = repo / "docs" / "feature" / _FEATURE_ID
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        "# Feature Delta: reuse-first-genesis-probe\n\n"
        "## Wave: DESIGN / [REF] Reuse Analysis\n\n"
        "| Existing Component | Justification |\n"
        "|---------------------|----------------|\n"
        f"| {component_name} | this feature's own genuinely new component |\n",
        encoding="utf-8",
    )


def _run_gate(repo: Path, *, base_branch: str | None = None) -> tuple[int, list[str]]:
    """Invoke the REAL gate ``main()`` in-process; return (exit_code, stdout_lines)."""
    cli_module = importlib.import_module(_CLI_MODULE)
    argv = ["--feature-id", _FEATURE_ID, "--repo-root", str(repo)]
    if base_branch is not None:
        argv += ["--base-branch", base_branch]
    exit_code = cli_module.main(argv)
    return exit_code, []


def test_long_lived_branch_foreign_commits_no_longer_pollute_this_features_reuse_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The RED-for-the-defect scenario: several unrelated, ALREADY-LANDED
    features' commits sit between master and this feature's genesis on the
    SAME long-lived branch. Before the fix, the unscoped `master...HEAD`
    diff counts those foreign classes as THIS feature's own NEW components
    -- none of them justified in THIS feature's Reuse Analysis table -- and
    the gate FAILs a feature that, on its own merits, is fully justified.
    """
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-q", "-b", "long-lived-integration")

    # Two OTHER, already-landed features' commits on the SAME long-lived
    # branch -- each introduces a class with NO relationship to the feature
    # under test, and NOT named in ITS Reuse Analysis table.
    _commit(
        repo,
        "src/other_feature_one.py",
        "class ForeignComponentOne():\n    pass\n",
        "feat: other feature one lands its own component",
    )
    _commit(
        repo,
        "src/other_feature_two.py",
        "class ForeignComponentTwo():\n    pass\n",
        "feat: other feature two lands its own component",
    )

    # THIS feature's own genesis: its feature-delta.md first enters history,
    # justifying ONLY its own new component.
    _write_feature_delta_justifying(repo, "OwnComponent")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"docs(feature): {_FEATURE_ID} feature-delta")

    # THIS feature's own new, justified component.
    _commit(
        repo,
        "src/own_feature.py",
        "class OwnComponent():\n    pass\n",
        "feat: this feature's own justified component",
    )

    exit_code, _ = _run_gate(repo)
    stdout = capsys.readouterr().out

    assert exit_code == 0, (
        "the gate must PASS once scoped to this feature's own genesis-to-HEAD "
        "range -- the two foreign, already-landed components from OTHER "
        f"features on this long-lived branch must not count against THIS "
        f"feature's Reuse Analysis. stdout={stdout!r}"
    )
    assert (
        "ForeignComponentOne" not in stdout and "ForeignComponentTwo" not in stdout
    ), (
        "the foreign components from other, already-landed features must not "
        f"even be DETECTED once the diff is scoped to this feature's own "
        f"genesis parent -- stdout={stdout!r}"
    )


def test_explicit_base_branch_still_overrides_genesis_resolution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An EXPLICIT ``--base-branch`` must still win over genesis resolution
    -- additivity guard: every existing caller that already passes
    ``--base-branch`` keeps its exact prior behavior.
    """
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-q", "-b", "feature/topic")
    _write_feature_delta_justifying(repo, "OwnComponent")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"docs(feature): {_FEATURE_ID} feature-delta")
    _commit(
        repo,
        "src/own_feature.py",
        "class OwnComponent():\n    pass\n",
        "feat: this feature's own justified component",
    )

    exit_code, _ = _run_gate(repo, base_branch="master")
    capsys.readouterr()

    assert exit_code == 0, (
        "an explicit --base-branch=master must still work exactly as before "
        f"(genesis resolution is a DEFAULT, not a forced override): exit={exit_code}"
    )


def test_default_still_resolves_when_feature_delta_has_no_git_history_yet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A brand-new, not-yet-committed feature-delta (the walking-skeleton
    case: ``git-diff-source`` fixture-injection path, or a feature-delta
    that only exists on the working tree) has no genesis commit to resolve
    -- the gate must fall back to ``resolve_default_base_ref`` (here:
    ``master`` itself, since that's the only real branch) rather than
    crashing or refusing to run.
    """
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-q", "-b", "feature/topic")
    _write_feature_delta_justifying(repo, "OwnComponent")
    # Deliberately do NOT commit the feature-delta -- it has no git history.
    _commit(
        repo,
        "src/own_feature.py",
        "class OwnComponent():\n    pass\n",
        "feat: this feature's own justified component",
    )

    exit_code, _ = _run_gate(repo)
    capsys.readouterr()

    assert exit_code == 0, (
        "an uncommitted feature-delta must fall back to the repo's resolved "
        f"trunk (master) rather than crashing: exit={exit_code}"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
