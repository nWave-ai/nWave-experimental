"""P0.1 fresh-clone gate — the observed proofs, pinned as regression.

These three tests ARE the evolution-plan P0.1 done-currency, made permanent:
the gate was proven by execution against a planted defect of its target class
(a dependency that exists in the working tree but is NOT committed — the
"works only on my machine" class the eval'd repo shipped), a clean case, and
the degrade-LOUD case. Deleting the gate's logic turns these RED.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli.verify_fresh_clone import main


_RECIPE = '{"steps": [{"name": "build", "cmd": ["python3", "main.py"]}]}\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _write_project(repo: Path) -> None:
    (repo / "main.py").write_text("import helper\nprint(helper.GREETING)\n")
    (repo / "helper.py").write_text('GREETING = "ok"\n')
    (repo / ".nwave").mkdir()
    (repo / ".nwave" / "demo-recipe.json").write_text(_RECIPE)


def test_planted_uncommitted_dependency_is_refused(tmp_path: Path) -> None:
    """NEGATIVE proof: works in the working tree, fails in the fresh export.

    helper.py is deliberately NOT committed. Local inspection (and a local
    run) says done; the committed tree does not contain the dependency, so
    the gate must go RED (exit 1) — never a silent pass.
    """
    repo = tmp_path / "planted"
    repo.mkdir()
    _init_repo(repo)
    _write_project(repo)
    _git(repo, "add", "main.py", ".nwave/demo-recipe.json")  # NOT helper.py
    _git(repo, "commit", "-qm", "planted: depends on untracked helper")

    assert main(["--repo", str(repo)]) == 1


def test_committed_project_is_verified(tmp_path: Path) -> None:
    """POSITIVE proof: the fully committed tree passes (exit 0)."""
    repo = tmp_path / "clean"
    repo.mkdir()
    _init_repo(repo)
    _write_project(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "complete committed project")

    assert main(["--repo", str(repo)]) == 0


def test_missing_recipe_degrades_loud_indeterminate(
    tmp_path: Path, capsys: object
) -> None:
    """DEGRADE proof: no recipe -> exit 2 with what/why/how, never a pass."""
    repo = tmp_path / "norecipe"
    repo.mkdir()
    _init_repo(repo)
    (repo / "f").write_text("x")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", "no recipe")

    assert main(["--repo", str(repo)]) == 2
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    event = json.loads(out.splitlines()[0])
    assert event["event"] == "FreshCloneIndeterminate"
    assert all(k in event for k in ("what", "why", "how"))
