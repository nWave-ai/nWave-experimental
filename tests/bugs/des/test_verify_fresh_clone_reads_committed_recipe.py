"""Regression: ``des verify-fresh-clone`` reads the demo recipe from the
WORKING TREE instead of the COMMITTED export it just built -- a false-green.

RCA (code-grounded, verified by a sister instance on her own repo):
``src/des/cli/verify_fresh_clone.py::main`` (~:252) calls
``_load_recipe(repo)`` -- which reads ``repo / RECIPE_RELPATH``
(``.nwave/demo-recipe.json``), the WORKING TREE (see ``_load_recipe``,
~:85-87) -- BEFORE ``_export_committed_tree`` (~:258) runs ``git archive
HEAD`` into a fresh temp export. So when ``.nwave/demo-recipe.json`` is
UNTRACKED (or gitignored), ``_load_recipe`` still finds it in the working
tree, parses its steps, and the gate RUNS them against the committed export
and emits ``FreshCloneVerified`` -- even though the export (a REAL fresh
clone) does not and cannot contain that recipe. The gate's own docstring
promises verification "in a fresh export of the COMMITTED tree"; an
untracked recipe breaks that promise silently.

The fix direction (NOT implemented here -- test-authoring only, zero
``src/`` edits): read the recipe from the EXPORT (``dest``) AFTER
``_export_committed_tree``, not from ``repo`` before it. A recipe absent
from the export must degrade to INDETERMINATE naming the committed-tree
absence -- never a silent pass, never an overcorrected refusal of a
genuinely committed recipe.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.verify_fresh_clone.main(argv)`` CLI entry, driven in-process
against a throwaway real git repo built under ``tmp_path`` (``git
init``/``add``/``commit`` via subprocess), JSON events captured via
``capsys``.

GIT SAFETY: every throwaway repo below is built with ``git`` invocations
scoped to ``cwd=<tmp_path repo>`` only (``_git(root, *args)``) -- LOCAL git
config only (``git config user.email``/``user.name`` with NO ``--global``
flag), never any git write against the real project repo.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli import verify_fresh_clone as vfc


# ---------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """A real, minimal git work-tree with a committed HEAD -- LOCAL config
    only, never ``--global``.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin hooksPath to the repo's own .git/hooks so no ambient global hook
    # config can interfere with this throwaway repo's commits.
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    (root / "README.md").write_text("base commit\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


_TRIVIAL_RECIPE = {"steps": [{"name": "noop", "cmd": ["true"]}]}


def _write_recipe(repo: Path, *, committed: bool) -> Path:
    """Write ``.nwave/demo-recipe.json`` with trivial always-passing steps.

    ``committed=False`` leaves it UNTRACKED (the false-green reproduction --
    a real fresh clone / ``git archive HEAD`` export can never contain it).
    ``committed=True`` commits it (the genuinely-verifiable world).
    """
    recipe_dir = repo / ".nwave"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = recipe_dir / "demo-recipe.json"
    recipe_path.write_text(json.dumps(_TRIVIAL_RECIPE), encoding="utf-8")
    if committed:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "chore: commit demo recipe")
    return recipe_path


def _run_gate(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[int, list[dict[str, object]]]:
    """Drive the REAL ``des verify-fresh-clone`` CLI in-process, capturing
    every emitted JSON event line (there can be several -- StepStarted /
    StepPassed / Verified, or a single Indeterminate).
    """
    exit_code = vfc.main(["--repo", str(repo)])
    stdout = capsys.readouterr().out
    events = [
        json.loads(line) for line in stdout.splitlines() if line.strip().startswith("{")
    ]
    return exit_code, events


# ===========================================================================
# 1. POSITIVE (the bug) -- RED today: untracked recipe false-greens the gate
# ===========================================================================


def test_untracked_recipe_is_not_verified_against_the_committed_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An UNTRACKED ``.nwave/demo-recipe.json`` must never make the gate
    emit ``FreshCloneVerified`` -- the fresh export (``git archive HEAD``)
    provably cannot contain an untracked file, so "verified in a fresh
    export of the committed tree" would be a lie. The gate must degrade to
    INDETERMINATE, naming the recipe's absence from the committed tree as
    the reason.

    RED for the right reason TODAY: ``main`` calls ``_load_recipe(repo)``
    (the WORKING TREE) before the export happens, so it happily finds and
    runs the untracked trivial-passing recipe against the export dir and
    emits ``FreshCloneVerified`` -- a real, semantic false-green, not a
    collection/import/setup error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_recipe(repo, committed=False)

    exit_code, events = _run_gate(repo, capsys)

    verified_events = [e for e in events if e.get("event") == "FreshCloneVerified"]
    assert not verified_events, (
        "an UNTRACKED .nwave/demo-recipe.json must never verify a fresh-clone "
        "export that cannot possibly contain it -- this is the false-green "
        f"bug itself. Got FreshCloneVerified event(s)={verified_events!r}, "
        f"all emitted events={events!r}"
    )
    assert exit_code == vfc._EXIT_INDETERMINATE, (
        "an untracked recipe cannot be honestly verified against the "
        f"COMMITTED-tree export -- expected exit_code={vfc._EXIT_INDETERMINATE} "
        f"(INDETERMINATE), got exit_code={exit_code!r}, events={events!r}"
    )
    indeterminate_events = [
        e for e in events if e.get("event") == "FreshCloneIndeterminate"
    ]
    assert indeterminate_events, (
        f"expected a FreshCloneIndeterminate event, got events={events!r}"
    )
    reason = " ".join(
        str(indeterminate_events[-1].get(k, "")) for k in ("what", "why", "how")
    ).lower()
    assert "committed" in reason, (
        "the INDETERMINATE reason must name the recipe's absence from the "
        f"COMMITTED tree as the cause -- got reason text={reason!r}, "
        f"event={indeterminate_events[-1]!r}"
    )


# ===========================================================================
# 2. NEGATIVE (two-worlds-must-not-collapse) -- must clear BEFORE and AFTER
# ===========================================================================


@pytest.mark.negative_at
def test_committed_recipe_is_never_refused_as_absent_from_the_committed_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A GENUINELY COMMITTED ``.nwave/demo-recipe.json`` -- the SAME trivial
    always-passing recipe, but actually committed to HEAD -- must reach
    verification. The fix for the untracked-recipe false-green must not
    overcorrect into refusing a recipe that IS in the committed export: the
    two worlds (untracked -> refuse; committed -> proceed) must not
    collapse into each other.

    Must stay GREEN both before and after the fix: today's code already
    reads (and finds) this recipe in the working tree since it is
    identical to the committed one; after the fix it will be read from
    the export instead, where it is equally present.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_recipe(repo, committed=True)

    exit_code, events = _run_gate(repo, capsys)

    assert not any(e.get("event") == "FreshCloneIndeterminate" for e in events), (
        "a genuinely COMMITTED recipe must never trigger the "
        "refused-as-absent-from-the-committed-tree INDETERMINATE path -- "
        f"got events={events!r}"
    )
    assert exit_code == 0, (
        "a committed trivial-passing recipe must verify cleanly -- "
        f"exit_code={exit_code!r}, events={events!r}"
    )
    assert any(e.get("event") == "FreshCloneVerified" for e in events), (
        "expected a FreshCloneVerified event for a committed trivial "
        f"recipe -- got events={events!r}"
    )
