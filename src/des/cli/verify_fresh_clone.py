"""``des verify-fresh-clone`` -- the P0.1 evidence-by-execution gate.

Expectation (evolution-plan P0.1): a build broken on a FRESH CLONE of the
committed tree cannot reach done. The eval'd seat-booking repo shipped with
``npm ci`` failing on a fresh clone and a Dockerfile that could not run --
invisible to every inspection because every inspector worked in the warm
working tree. This gate exports the COMMITTED tree (``git archive``, so
uncommitted/untracked files are excluded by construction -- the
"works-only-on-my-machine" class fails here) into a temp dir and executes the
project's declared demo recipe start to finish.

Recipe (target-project-declared, language-agnostic): ``.nwave/demo-recipe.json``

    {
      "steps": [
        {"name": "install", "cmd": ["npm", "ci"]},
        {"name": "build",   "cmd": ["npm", "run", "build"]},
        {"name": "golden",  "cmd": ["npm", "run", "e2e:golden"]}
      ],
      "timeout_seconds": 600
    }

Verdicts (degrade-LOUD, never silent-pass; every failure states WHAT failed,
WHY, and HOW to fix -- the standing what/why/how rule):

    0  FreshCloneVerified      -- every recipe step exited 0 in the fresh export
    1  FreshCloneRefused       -- a step failed; the payload names step, exit
                                  code, and output tail
    2  FreshCloneIndeterminate -- the gate could not run (no recipe, no git,
                                  not a repo, malformed recipe); NEVER a pass

Python + stdlib only. ``git`` is consulted as an optional external tool per
the target-machine-agnosticism constraint: its absence degrades LOUD to
INDETERMINATE, never a crash and never a silent pass.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


RECIPE_RELPATH = Path(".nwave") / "demo-recipe.json"
_DEFAULT_STEP_TIMEOUT_SECONDS = 600
_OUTPUT_TAIL_CHARS = 2000

_EXIT_VERIFIED = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2


@dataclass(frozen=True)
class _RecipeStep:
    """One declared step of the target project's demo recipe."""

    name: str
    cmd: tuple[str, ...]
    timeout_seconds: int


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload))


def _indeterminate(what: str, why: str, how: str) -> int:
    _emit(
        {
            "event": "FreshCloneIndeterminate",
            "what": what,
            "why": why,
            "how": how,
        }
    )
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _load_recipe(repo: Path) -> list[_RecipeStep] | int:
    """Parse the recipe or return the LOUD indeterminate exit code."""
    recipe_path = repo / RECIPE_RELPATH
    if not recipe_path.is_file():
        return _indeterminate(
            what=f"no demo recipe at {RECIPE_RELPATH}",
            why=(
                "the fresh-clone gate executes the project's own declared "
                "install/build/run steps; without a recipe there is nothing "
                "honest to execute (a silent pass here is the disease)."
            ),
            how=(
                f'create {RECIPE_RELPATH} with {{"steps": [{{"name": "build", '
                '"cmd": ["<your-build-cmd>", "..."]}]} and commit it.'
            ),
        )
    try:
        raw = json.loads(recipe_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _indeterminate(
            what=f"unreadable/malformed recipe {RECIPE_RELPATH}",
            why=str(exc),
            how="fix the JSON and re-run.",
        )
    default_timeout = raw.get("timeout_seconds", _DEFAULT_STEP_TIMEOUT_SECONDS)
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        return _indeterminate(
            what="recipe has no steps",
            why="an empty recipe would make the gate a silent pass.",
            how='declare at least one {"name", "cmd": [...]} step.',
        )
    steps: list[_RecipeStep] = []
    for i, entry in enumerate(steps_raw):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("name"), str)
            or not isinstance(entry.get("cmd"), list)
            or not entry["cmd"]
            or not all(isinstance(c, str) for c in entry["cmd"])
        ):
            return _indeterminate(
                what=f"malformed recipe step #{i}",
                why='each step needs a "name" (str) and a non-empty "cmd" (list of str).',
                how="fix the step and re-run.",
            )
        timeout = entry.get("timeout_seconds", default_timeout)
        steps.append(
            _RecipeStep(
                name=entry["name"],
                cmd=tuple(entry["cmd"]),
                timeout_seconds=int(timeout),
            )
        )
    return steps


def _export_committed_tree(repo: Path, dest: Path) -> int | None:
    """``git archive HEAD`` -> extract into ``dest`` (stdlib tarfile).

    The COMMITTED tree only: uncommitted edits and untracked files are absent
    by construction, so "works only because of my working tree" fails here.
    Returns the indeterminate exit code on degrade, None on success.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", "HEAD"],
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        return _indeterminate(
            what="git is not available on this machine",
            why="the gate exports the COMMITTED tree via `git archive`.",
            how="install git, or run the gate on a machine that has it.",
        )
    except subprocess.TimeoutExpired:
        return _indeterminate(
            what="`git archive HEAD` timed out",
            why="the repository did not answer within 120s.",
            how="check repository health and re-run.",
        )
    if proc.returncode != 0:
        return _indeterminate(
            what=f"`git archive HEAD` failed (exit {proc.returncode})",
            why=proc.stderr.decode(errors="replace")[-_OUTPUT_TAIL_CHARS:],
            how="run it manually in the repo; the gate needs a committed HEAD.",
        )
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
        tar.extractall(dest, filter="data")
    return None


def _run_steps(steps: list[_RecipeStep], workdir: Path) -> int:
    for step in steps:
        _emit(
            {
                "event": "FreshCloneStepStarted",
                "step": step.name,
                "cmd": list(step.cmd),
            }
        )
        try:
            proc = subprocess.run(
                list(step.cmd),
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
            )
        except FileNotFoundError:
            _emit(
                {
                    "event": "FreshCloneRefused",
                    "what": f"step '{step.name}' command not found: {step.cmd[0]}",
                    "why": "the tool the recipe declares is not on this machine's PATH.",
                    "how": f"install {step.cmd[0]!r} or fix the recipe command.",
                }
            )
            print(f"✗ REFUSED — step '{step.name}': command not found ({step.cmd[0]})")
            return _EXIT_REFUSED
        except subprocess.TimeoutExpired:
            _emit(
                {
                    "event": "FreshCloneRefused",
                    "what": f"step '{step.name}' timed out after {step.timeout_seconds}s",
                    "why": "the declared step did not finish in a fresh clone.",
                    "how": "run the step in a fresh clone yourself; fix or re-budget it.",
                }
            )
            print(f"✗ REFUSED — step '{step.name}' timed out ({step.timeout_seconds}s)")
            return _EXIT_REFUSED
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-_OUTPUT_TAIL_CHARS:]
            _emit(
                {
                    "event": "FreshCloneRefused",
                    "what": (
                        f"step '{step.name}' failed (exit {proc.returncode}) "
                        "in a FRESH export of the committed tree"
                    ),
                    "why": tail,
                    "how": (
                        "reproduce with: git archive HEAD | tar -x -C <tmp> && "
                        f"cd <tmp> && {' '.join(step.cmd)} — then fix and COMMIT "
                        "the fix (an uncommitted fix will fail here again)."
                    ),
                }
            )
            print(f"✗ REFUSED — step '{step.name}' exit {proc.returncode}")
            return _EXIT_REFUSED
        _emit({"event": "FreshCloneStepPassed", "step": step.name})
    return _EXIT_VERIFIED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-fresh-clone",
        description=(
            "Execute the project's declared demo recipe in a fresh export of "
            "the COMMITTED tree (evidence-by-execution gate, evolution P0.1)."
        ),
    )
    parser.add_argument("--repo", default=".", help="Path to the git repository.")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    steps_or_exit = _load_recipe(repo)
    if isinstance(steps_or_exit, int):
        return steps_or_exit

    with tempfile.TemporaryDirectory(prefix="nwave-fresh-clone-") as tmp:
        dest = Path(tmp)
        degrade = _export_committed_tree(repo, dest)
        if degrade is not None:
            return degrade
        exit_code = _run_steps(steps_or_exit, dest)

    if exit_code == _EXIT_VERIFIED:
        _emit(
            {
                "event": "FreshCloneVerified",
                "steps": [s.name for s in steps_or_exit],
            }
        )
        print(f"✓ PASS — fresh clone verified ({len(steps_or_exit)} steps)")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
