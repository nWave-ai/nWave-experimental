"""Falsifier for the new pre-commit gate
(scripts/hooks/check_retired_subcommand_declared.py): a `des` subcommand
silently dropped from `_REGISTRY` without a matching `_RETIRED` entry must
block the commit; declaring it must unblock the same commit.

Follow-up to F-INSTALL-REMOVAL-TRANSPARENCY (Ale): the fix reproduced one
level up the same defect it repaired -- nothing stopped a future silent
removal from skipping `_RETIRED`. This test exercises the REAL gate
end-to-end against a real (throwaway) git repo, not only the pure
predicate: the mandate explicitly asked for a falsifier that can fail for
real, not a fifth gate that declares what it does not check.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hooks"
    / "check_retired_subcommand_declared.py"
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_retired_subcommand_declared", _HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_MODULE = _load()
_PREDICATE = _MODULE.undeclared_removed_names


# ---------------------------------------------------------------------------
# Pure predicate -- fast, isolated
# ---------------------------------------------------------------------------


def test_flags_a_removed_name_absent_from_retired() -> None:
    old = frozenset({"a", "b", "c"})
    new = frozenset({"a", "b"})
    retired = frozenset()

    assert _PREDICATE(old, new, retired) == frozenset({"c"})


def test_clears_when_the_removed_name_is_declared_retired() -> None:
    old = frozenset({"a", "b", "c"})
    new = frozenset({"a", "b"})
    retired = frozenset({"c"})

    assert _PREDICATE(old, new, retired) == frozenset()


def test_ignores_added_names() -> None:
    old = frozenset({"a"})
    new = frozenset({"a", "brand-new"})
    retired = frozenset()

    assert _PREDICATE(old, new, retired) == frozenset()


def test_no_removal_no_flag() -> None:
    old = frozenset({"a", "b"})
    new = frozenset({"a", "b"})
    retired = frozenset()

    assert _PREDICATE(old, new, retired) == frozenset()


# ---------------------------------------------------------------------------
# Real end-to-end: a throwaway git repo, the actual hook's main()
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "HOME": str(cwd),
            "PATH": "/usr/bin:/bin",
        },
    )


def _write_main(path: Path, names: list[str], retired: list[str]) -> None:
    rows = "\n".join(
        f'    _SubcommandRow("{n}", "des.cli.{n.replace("-", "_")}", "main"),'
        for n in names
    )
    retired_entries = ", ".join(f'"{r}"' for r in retired)
    path.write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class _SubcommandRow:\n"
        "    name: str\n"
        "    module_path: str\n"
        "    function_name: str\n\n\n"
        "_REGISTRY = (\n" + rows + "\n)\n\n"
        f"_RETIRED = {{name: object() for name in ({retired_entries}"
        + ("," if len(retired) == 1 else "")
        + ")}\n",
        encoding="utf-8",
    )


@pytest.fixture
def toy_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with the exact relative path the hook targets:
    `src/des/cli/__main__.py`, committed once at HEAD with 3 subcommands."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    _git("config", "user.email", "test@example.invalid", cwd=repo)

    main_file = repo / "src" / "des" / "cli" / "__main__.py"
    main_file.parent.mkdir(parents=True)
    _write_main(main_file, names=["alpha", "beta", "gamma"], retired=[])
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "initial", cwd=repo)
    return repo


def _run_hook(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(_HOOK_PATH)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_red_silent_removal_without_retired_entry_blocks(toy_repo: Path) -> None:
    main_file = toy_repo / "src" / "des" / "cli" / "__main__.py"
    # Remove "gamma", declare nothing retired -- the exact defect class.
    _write_main(main_file, names=["alpha", "beta"], retired=[])
    _git("add", ".", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "gamma" in result.stderr
    assert "WHAT:" in result.stderr
    assert "WHY:" in result.stderr
    assert "HOW:" in result.stderr


def test_green_same_removal_with_retired_entry_passes(toy_repo: Path) -> None:
    main_file = toy_repo / "src" / "des" / "cli" / "__main__.py"
    # Same removal, this time declared.
    _write_main(main_file, names=["alpha", "beta"], retired=["gamma"])
    _git("add", ".", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_unrelated_commit_not_touching_the_file_is_untouched(toy_repo: Path) -> None:
    (toy_repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_pure_addition_with_no_removal_passes_without_retired(toy_repo: Path) -> None:
    main_file = toy_repo / "src" / "des" / "cli" / "__main__.py"
    _write_main(main_file, names=["alpha", "beta", "gamma", "delta"], retired=[])
    _git("add", ".", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 0, result.stdout + result.stderr
