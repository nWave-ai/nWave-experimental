"""Falsifier for the documentation-staleness ratchet
(scripts/hooks/check_no_new_ghost_verb_citations.py): a staged `.md` file
citing a `des <verb>` not in the live `_REGISTRY` and not already in the
known-debt baseline must block the commit; the same citation already
present in the baseline must not.

F-INSTALL-REMOVAL-TRANSPARENCY follow-up (Ale): the existing ~500-pair
debt cannot make this gate zero-tolerance without it being disarmed within
a day, so it ratchets against a checked-in baseline instead. This test
proves the ratchet direction with a real, throwaway git repo and the
actual hook script, not only the pure predicate -- the mandate explicitly
asked for a falsifier that can fail for real.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hooks"
    / "check_no_new_ghost_verb_citations.py"
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_no_new_ghost_verb_citations", _HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_MODULE = _load()
_PREDICATE = _MODULE.new_ghost_citations


# ---------------------------------------------------------------------------
# Pure predicate -- fast, isolated
# ---------------------------------------------------------------------------


def test_flags_a_ghost_verb_absent_from_the_baseline() -> None:
    current = {"docs/x.md": frozenset({"brand-new-ghost"})}
    baseline: dict[str, frozenset[str]] = {}

    assert _PREDICATE(current, baseline) == {
        "docs/x.md": frozenset({"brand-new-ghost"})
    }


def test_does_not_flag_a_ghost_verb_already_in_the_baseline() -> None:
    current = {"docs/x.md": frozenset({"commit-slice"})}
    baseline = {"docs/x.md": frozenset({"commit-slice"})}

    assert _PREDICATE(current, baseline) == {}


def test_flags_only_the_new_verb_when_file_has_both() -> None:
    current = {"docs/x.md": frozenset({"commit-slice", "brand-new-ghost"})}
    baseline = {"docs/x.md": frozenset({"commit-slice"})}

    assert _PREDICATE(current, baseline) == {
        "docs/x.md": frozenset({"brand-new-ghost"})
    }


def test_a_new_file_with_a_known_ghost_verb_is_flagged() -> None:
    """Baseline has no entry for this file at all -- everything in it is
    new by definition."""
    current = {"docs/never-seen-before.md": frozenset({"commit-slice"})}
    baseline: dict[str, frozenset[str]] = {}

    assert _PREDICATE(current, baseline) == {
        "docs/never-seen-before.md": frozenset({"commit-slice"})
    }


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


def _write_main(path: Path, names: list[str]) -> None:
    rows = "\n".join(
        f'    _SubcommandRow("{n}", "des.cli.{n.replace("-", "_")}", "main"),'
        for n in names
    )
    path.write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class _SubcommandRow:\n"
        "    name: str\n"
        "    module_path: str\n"
        "    function_name: str\n\n\n"
        "_REGISTRY = (\n" + rows + "\n)\n",
        encoding="utf-8",
    )


@pytest.fixture
def toy_repo(tmp_path: Path) -> Path:
    """A throwaway repo with the real relative paths both this gate and the
    sibling registry-diff gate target, plus a baseline seeding one known
    ghost verb for one file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    _git("config", "user.email", "test@example.invalid", cwd=repo)

    main_file = repo / "src" / "des" / "cli" / "__main__.py"
    main_file.parent.mkdir(parents=True)
    _write_main(main_file, names=["alpha", "beta"])

    baseline_file = repo / "nWave" / "data" / "ghost-verb-citation-baseline.json"
    baseline_file.parent.mkdir(parents=True)
    baseline_file.write_text(
        json.dumps({"files": {"docs/known.md": ["known-ghost"]}}),
        encoding="utf-8",
    )

    known_doc = repo / "docs" / "known.md"
    known_doc.parent.mkdir(parents=True)
    known_doc.write_text("Run `des known-ghost --flag` for this.\n", encoding="utf-8")

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


def test_red_new_ghost_citation_in_a_new_file_blocks(toy_repo: Path) -> None:
    new_doc = toy_repo / "docs" / "new.md"
    new_doc.write_text("Run `des never-existed-verb --now` please.\n", encoding="utf-8")
    _git("add", ".", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "never-existed-verb" in result.stderr
    assert "docs/new.md" in result.stderr
    assert "WHAT:" in result.stderr
    assert "WHY:" in result.stderr
    assert "HOW:" in result.stderr


def test_green_the_already_baselined_citation_passes(toy_repo: Path) -> None:
    known_doc = toy_repo / "docs" / "known.md"
    # Re-save unchanged -- still cites the same already-baselined ghost verb.
    known_doc.write_text(
        known_doc.read_text(encoding="utf-8") + "\nSame ghost verb again.\n",
        encoding="utf-8",
    )
    _git("add", ".", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_green_a_new_file_citing_a_live_verb_passes(toy_repo: Path) -> None:
    new_doc = toy_repo / "docs" / "fine.md"
    new_doc.write_text("Run `des alpha` for this.\n", encoding="utf-8")
    _git("add", ".", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_unrelated_non_markdown_staged_file_is_untouched(toy_repo: Path) -> None:
    (toy_repo / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git("add", "code.py", cwd=toy_repo)

    result = _run_hook(toy_repo)

    assert result.returncode == 0, result.stdout + result.stderr
