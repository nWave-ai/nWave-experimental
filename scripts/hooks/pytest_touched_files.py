#!/usr/bin/env python3
"""Pre-commit test gate scoped to the files the commit actually TOUCHES.

WHY THIS EXISTS
---------------
Measured 2026-08-22 (`F-LOCAL-GATE-COVERAGE-1-2-PERCENT`): the local safety net
selected **78 of 6548** collected tests -- `pytest-fast-gate` 15, `pytest-e2e`
63, `pytest-quick-tiers` 0 (`stages: [manual]`, retired 2026-07-18). **No tier
was covered**: unit 5273/14, acceptance 1230/1, integration 67/0. Any defect
outside those 78 tests entered the trunk without meeting anything, and two
regressions plus a days-long broken public install were the bill already paid.

The marker-based selectors were the wrong AXIS. A marker names a TIER; a commit
touches FILES. This gate selects on the axis the commit actually moves, so every
tier is reachable: if a touched file has a unit test, the unit tier runs; if it
has an acceptance test, the acceptance tier runs.

SELECTION (pure Python, stdlib only -- no new dependency; see "REJECTED" below)
------------------------------------------------------------------------------
pre-commit hands us the staged paths on argv (``pass_filenames: true``), so this
script never shells out to git.

1. Touched **test** file (``tests/**/*.py``) -> runs, always. Non-``.py`` files
   under ``tests/`` (``.feature`` and friends) -> the ``.py`` test files sitting
   in the SAME directory run.
2. Touched **source** file (``src/**``, ``scripts/**``, ``nwave_ai/**``) -> its
   dotted module name is resolved (both ``des.x.y`` and ``src.des.x.y`` spellings)
   and every test file that REFERENCES that module runs. A reference is an
   import, a ``from pkg import mod``, or a ``patch("des.x.y.Thing")`` target --
   all three are the same dotted string in the file text.
3. Touched **asset / config** file -> a small prefix map (``nWave/`` ->
   ``tests/build`` + ``tests/framework``, ``.pre-commit-config.yaml`` ->
   ``tests/build``, ...). Anything unmapped is declared UNCOVERED **out loud**,
   by name, on stderr -- never silently skipped (GDP-6).

Direct references only, ONE hop. Transitive closure was built and MEASURED
first: 4 hops over the src import graph selected 688 of 970 test files for a
single leaf module -- i.e. the whole suite, ~30 min, useless as a commit gate.
One hop is the honest, bounded answer; the transitive gap is real and named in
"KNOWN GAPS" below rather than papered over.

EXCLUSIONS (declared, with the reason -- GDP-6, no silent narrowing)
-------------------------------------------------------------------
``**/e2e/**``, ``polyglot-pilot`` and ``tests/build/acceptance/`` are dropped
from the selection and announced: they are testcontainers/Docker and
multi-language-compile tiers costing minutes each, which is a pre-push/CI cost,
not a per-commit one. They keep their existing pre-push stage.

REJECTED ALTERNATIVES
---------------------
* **pytest-testmon** -- a genuine coverage-derived mapping, but a NEW runtime
  dependency whose ``.testmondata`` must be bootstrapped by a full-suite run
  (~30 min) and re-bootstrapped whenever it is invalidated. The repo's
  portability invariant is pure Python; the mapping above needs no database and
  no bootstrap.
* **the existing ``scripts/hooks/validate_tests.py`` mapping** -- reused in
  SPIRIT (its prefix table is where ``_ASSET_PREFIX_TESTS`` comes from) but not
  in FORM: it maps a source file to a whole test DIRECTORY (``src/des/`` ->
  ``tests/des/``, i.e. 5000+ tests) and falls back to the FULL SUITE on any
  unrecognised path. Both are minutes-to-tens-of-minutes at commit time on this
  box, and a full-suite fallback at commit time is the exact box-saturation
  hazard that corrupts ``.git`` here.

KNOWN GAPS (named, not hidden)
------------------------------
* Indirect impact is not followed: touching ``a.py`` does not select the tests
  of ``b.py`` that imports it. Measured cost of closing it: the whole suite.
* Dynamic imports built from runtime-assembled strings are invisible to a
  textual reference scan.
* The dropped tiers above are covered at pre-push/CI only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

TESTS_ROOT = "tests"
SOURCE_ROOTS = ("src/", "scripts/", "nwave_ai/")

# Paths whose cost is minutes each (Docker / multi-language compile). Excluded
# from the per-commit selection ON PURPOSE and announced when excluded.
_DEFERRED_TO_PREPUSH = (
    "/e2e/",
    "tests/e2e/",
    "polyglot-pilot",
    "tests/build/acceptance/",
)

# Non-Python assets -> the test directories that assert on them. Derived from
# the prefix table in scripts/hooks/validate_tests.py (same repo convention).
_ASSET_PREFIX_TESTS: dict[str, tuple[str, ...]] = {
    "nWave/": ("tests/build", "tests/framework"),
    ".pre-commit-config.yaml": ("tests/build",),
    "pyproject.toml": ("tests/build",),
    ".github/": ("tests/build",),
}

# Box-safety ceiling. RE-MEASURED 2026-08-23 AFTER the two selector
# corrections (the is_collectible index fix and this ceiling itself): the
# widest REALISTIC commit (an asset touch mapping to tests/build +
# tests/framework) selects 88 test files / 746 tests / 21.1s, green. The
# earlier 40.5s figure was a FLOOR, not a cost: that run aborted early on a
# false red produced by the pre-fix index. Only a near-root conftest.py goes
# past this ceiling, and that is a suite-wide change whose right home is a
# deliberate run, not a commit hook.
MAX_TEST_FILES_PER_COMMIT = 200

# Files whose content is prose only: no test derives from them, and saying so is
# a decision, not an oversight.
_PROSE_ONLY_PREFIXES = ("docs/", "defects.md", "techdebt.md", "done.md", "README.md")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def module_names(rel_path: str) -> set[str]:
    """Dotted module spellings a test could import this file as.

    ``__init__.py`` yields nothing: its package name (``des``) is so coarse it
    matches every test file, which is how a first attempt at this selector
    silently degenerated into a full-suite run.
    """
    if not rel_path.endswith(".py"):
        return set()
    parts = rel_path[:-3].split("/")
    if parts[-1] == "__init__":
        return set()
    names = {".".join(parts)}
    if parts[0] == "src":
        names.add(".".join(parts[1:]))
    return {n for n in names if n.count(".") >= 1}


def references(text: str, module: str) -> bool:
    """Does this file text reference ``module``?

    Catches ``import des.x.y``, ``from des.x.y import Z``, ``patch("des.x.y.Z")``
    (all the literal dotted string) and ``from des.x import y`` (the split form).
    """
    if module in text:
        return True
    package, base = module.rsplit(".", 1)
    pattern = (
        r"from\s+"
        + re.escape(package)
        + r"\s+import\s+\(?[^\n)]*\b"
        + re.escape(base)
        + r"\b"
    )
    return bool(re.search(pattern, text))


def is_collectible(rel_path: str) -> bool:
    """Would pytest COLLECT this file? (default ``python_files`` convention.)

    Load-bearing, learned the hard way: a first cut indexed every ``.py`` under
    ``tests/`` and so selected ``__init__.py``, ``conftest.py`` and — worst —
    the deliberate-VIOLATION fixtures under ``tests/build/**/fixtures/`` that a
    meta-test collects on purpose to assert they fail. Running those directly
    made the gate reject a perfectly good commit. ``pyproject.toml`` sets no
    ``python_files``, so pytest's default is the contract.
    """
    name = rel_path.rsplit("/", 1)[-1]
    return name.endswith(".py") and (
        name.startswith("test_") or name.endswith("_test.py")
    )


def _test_files(root: Path) -> dict[str, str]:
    index: dict[str, str] = {}
    tests_dir = root / TESTS_ROOT
    if not tests_dir.is_dir():
        return index
    for path in tests_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if not is_collectible(rel):
            continue
        try:
            index[path.relative_to(root).as_posix()] = path.read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            continue
    return index


def _is_deferred(rel_path: str) -> bool:
    return any(marker in rel_path for marker in _DEFERRED_TO_PREPUSH)


def select(touched: list[str], root: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (test files to run, deferred paths, uncovered touched paths)."""
    index = _test_files(root)
    selected: set[str] = set()
    uncovered: list[str] = []

    for rel_path in touched:
        rel_path = rel_path.replace("\\", "/")

        if rel_path.startswith(TESTS_ROOT + "/"):
            if is_collectible(rel_path):
                if (root / rel_path).is_file():
                    selected.add(rel_path)
            else:
                # conftest.py, a .feature file, a fixture or a helper: pytest
                # never collects it directly, but it CONDITIONS everything in
                # its subtree. Run that subtree.
                subtree = rel_path.rsplit("/", 1)[0] + "/"
                selected.update(t for t in index if t.startswith(subtree))
            continue

        if rel_path.startswith(SOURCE_ROOTS) and rel_path.endswith(".py"):
            modules = module_names(rel_path)
            if not modules:
                uncovered.append(f"{rel_path} (package __init__, too coarse to key on)")
                continue
            hits = {
                t
                for t, text in index.items()
                if any(references(text, m) for m in modules)
            }
            if hits:
                selected.update(hits)
            else:
                uncovered.append(f"{rel_path} (no test file references it)")
            continue

        asset_dirs = next(
            (
                dirs
                for prefix, dirs in sorted(
                    _ASSET_PREFIX_TESTS.items(), key=lambda kv: len(kv[0]), reverse=True
                )
                if rel_path == prefix or rel_path.startswith(prefix)
            ),
            None,
        )
        if asset_dirs is not None:
            selected.update(
                t for t in index if t.startswith(tuple(d + "/" for d in asset_dirs))
            )
            continue

        if rel_path.startswith(_PROSE_ONLY_PREFIXES):
            continue

        uncovered.append(f"{rel_path} (no mapping rule)")

    deferred = sorted(t for t in selected if _is_deferred(t))
    runnable = sorted(t for t in selected if not _is_deferred(t))
    return runnable, deferred, uncovered


def _pytest_command(targets: list[str]) -> list[str]:
    args = [*targets, "--tb=short", "-q", "-x", "-p", "no:cacheprovider"]
    try:
        import importlib.util

        if importlib.util.find_spec("xdist") is not None and len(targets) > 3:
            # -n 2, never `auto`: this box is 4 cores / ~11GB and each xdist
            # worker loads the whole suite. Higher counts have OOM-corrupted
            # .git here before (RCA fix-speculative-test-pollution 2026-05-13).
            args.extend(["-n", "2", "--dist", "loadfile"])
    except Exception:
        pass
    return ["uv", "run", "python3", "-m", "pytest", *args]


def _clear_git_environment() -> None:
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_AUTHOR_DATE",
    ):
        os.environ.pop(var, None)


def main(argv: list[str]) -> int:
    root = _repo_root()
    touched = [a for a in argv if a and not a.startswith("-")]
    if not touched:
        print(f"{GREEN}Touched-file test gate: nothing staged.{NC}")
        return 0

    runnable, deferred, uncovered = select(touched, root)

    for entry in uncovered:
        print(f"{YELLOW}UNCOVERED at commit time: {entry}{NC}", file=sys.stderr)
    if deferred:
        print(
            f"{YELLOW}Deferred to pre-push/CI ({len(deferred)} file(s)): Docker/"
            f"multi-language tiers cost minutes each.{NC}",
            file=sys.stderr,
        )

    if not runnable:
        print(
            f"{GREEN}Touched-file test gate: no test file impacted by this commit.{NC}"
        )
        return 0

    if len(runnable) > MAX_TEST_FILES_PER_COMMIT:
        # Box-safety valve, and it says so instead of truncating to an arbitrary
        # subset. Reached only by a near-root conftest.py: this box is 4 cores /
        # ~11GB and a suite-wide run at commit time is the exact memory
        # saturation that has OOM-corrupted .git here.
        print(
            f"{YELLOW}NOT RUN at commit time: {len(runnable)} test files impacted, "
            f"above the per-commit ceiling of {MAX_TEST_FILES_PER_COMMIT}.{NC}",
            file=sys.stderr,
        )
        print(
            f"{YELLOW}  A commit this wide (near-root conftest / suite-wide "
            f"fixture) is a CI-scale change; run it deliberately:{NC}",
            file=sys.stderr,
        )
        print(f"{YELLOW}    uv run poe test-fast{NC}", file=sys.stderr)
        return 0

    print(f"{BLUE}Touched-file test gate: {len(runnable)} test file(s) impacted.{NC}")

    _clear_git_environment()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")

    # stdin=DEVNULL + an explicit bound: the execution-perimeter spawn invariant
    # (tests/build/test_no_unbounded_unstdin_spawn.py) bans a spawn that inherits
    # fd 0 or runs unbounded. A hang here would freeze the commit forever.
    try:
        result = subprocess.run(
            _pytest_command(runnable),
            check=False,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        print()
        print(
            f"{RED}COMMIT BLOCKED -- INDETERMINATE: the touched-file test run", end=""
        )
        print(f" exceeded its 1800s bound.{NC}")
        print("      A gate that cannot decide must not pass. Re-run the command")
        print("      printed above by hand to see where it hangs.")
        return 1

    if result.returncode in (0, 5):
        print(f"{GREEN}Touched-file test gate: green.{NC}")
        return 0

    print()
    print(f"{RED}COMMIT BLOCKED -- a test covering a file in this commit is RED.{NC}")
    print()
    print(f"{RED}WHAT{NC}  pytest failed over the {len(runnable)} test file(s) that")
    print("      reference the source files this commit touches (see the")
    print("      traceback above for the failing node).")
    print(f"{RED}WHY{NC}   Until 2026-08-23 the local gate selected 78 of 6548 tests")
    print("      by MARKER, so a defect in a touched file met nothing before")
    print("      reaching the trunk. This gate selects by TOUCHED FILE instead.")
    print(f"{RED}HOW{NC}   Reproduce exactly what just ran:")
    print(
        f"        uv run pytest {' '.join(runnable[:6])}"
        + (" ..." if len(runnable) > 6 else "")
    )
    print("      Fix the code or the test, then commit again.")
    print("      If the failure is unrelated to this commit, it is still a red")
    print("      test in a file you touched -- repair on sight, do not bypass.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
