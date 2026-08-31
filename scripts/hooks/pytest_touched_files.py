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

THE THIRD STATE: expected-red (added 2026-08-23, defect D-GATE-NO-EXPECTED-RED)
-------------------------------------------------------------------------------
A two-state gate -- pass or fail -- cannot express this project's normal DISTILL
flow. On the ``atdd_pure`` spine a ``RED_TO_GREEN`` contract's acceptance oracle
is authored BEFORE the code it verifies, so at the moment it is committed the
module under test does not exist and pytest cannot even COLLECT the file. The
gate scored that as a failure and would therefore have rejected EVERY DISTILL
commit that carries an oracle ahead of its implementation. That is not an edge
case; it is the mainline (measured 2026-08-23 on ``auto-0d64ca2e4b7ded7d``:
``ModuleNotFoundError: No module named 'des.cli.update'``, gate exit 1).

The fix is a THIRD state, and it is recognised by a **declared property**, never
by a convention. THE RULE DOES NOT LIVE HERE: it lives ONCE in
``src/des/domain/declared_red_oracles.py``, because the very same commit was
then rejected by a SECOND consumer (``pytest-fast-gate``, which collects the
whole tree) and the population is three gates, not one. This file OBSERVES the
property by running ``pytest --collect-only``; ``tests/conftest.py`` observes it
at ``pytest_make_collect_report`` and so covers every pytest-driven consumer.
Neither owns a second copy of the rule. In THIS repo the conftest translation
fires first, so this hook's own probe sees an already-translated SKIP rather
than the raw ``ModuleNotFoundError``, keeps the file in the normal run, and the
run is green because the oracle is skipped there too -- belt and braces over one
rule, never two rules. The probe still earns its keep for a test root that has
no nWave conftest (a polyglot or vendored subject). "Skip any test that fails to import" would be a sieve, strictly
worse than the defect. The declaration lives in the delivery contract, which is
the artefact that already knows the answer, and all THREE conjuncts must hold:

1. the test file is the ``acceptance-tests.locator`` of a contract under
   ``docs/delivery-contracts/`` whose ``delivery-route`` is ``RED_TO_GREEN``;
2. that contract is still OPEN -- at least one declared ``target`` is absent
   from disk. Every target present means the work landed, the oracle owes green,
   and no exemption exists for it;
3. the observed non-collection is a ``ModuleNotFoundError`` naming ONLY modules
   that ARE those absent declared targets. The reason is checked, not assumed.

Conjunct 3 is what keeps the discrimination honest, and it is observed, not
inferred: the gate actually runs ``pytest --collect-only`` on the candidate and
reads the error. An oracle that COLLECTS is never exempt -- it runs, and if it
is red it blocks (a declared oracle red for an UNDECLARED reason is a defect
like any other). A ``SyntaxError``, or a missing module that is not a declared
absent target, is likewise not exempt. Failing that check the file is simply
kept in the normal run, so every unknown resolves to the blocking behaviour.

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
* expected-red matches the reported missing module EXACTLY. If a whole absent
  package makes pytest report the ANCESTOR (``des.cli`` rather than
  ``des.cli.update``), the oracle is NOT exempted and the commit blocks. That is
  the fail-closed direction, and prefix matching is deliberately not implemented
  until a real commit needs it (GDP-10: no incident, no mechanism).
* expected-red covers ``ModuleNotFoundError`` only. An oracle whose declared
  target EXISTS but does not yet export the symbol the oracle imports raises
  ``ImportError: cannot import name`` and still blocks. Widening to that case
  would mask a real regression that deletes a symbol from an EXTEND target, so
  it stays closed until a commit demonstrates the need.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable


# ONE definition of the expected-red discrimination, shared with
# `tests/conftest.py` (see the module docstring of the import below: the
# second occurrence of this defect is what moved the rule out of this file).
# `src` is put on the path explicitly rather than assumed: this hook runs as
# bare `python3 scripts/hooks/pytest_touched_files.py`, with no `uv run` and no
# installed package, and the shared module is deliberately stdlib-only so that
# stays true.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from des._internal.delivery_contract_schema import (
    LEGACY_SCHEMA_VERSION,
    delivery_contract_schema_version,
)
from des.domain.declared_red_oracles import (
    declared_red_oracles,
    module_names,
)
from des.domain.declared_red_oracles import (
    expected_red_reason as _declared_reason,
)
from des.domain.repo_path_resolver import resolve_repo_root


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
_CLOSURE_INDEX = re.compile(r"nwave-delivery-[^.]+\.index\Z")
_CLOSURE_CONTRACT_PREFIX = "docs/delivery-contracts/"


def _repo_root() -> Path:
    return resolve_repo_root(None)


def _touched_relative_paths(touched: list[str]) -> set[str]:
    """Normalize the one Git spelling used by hook argv and contracts."""
    return {
        path.replace("\\", "/").removeprefix("./")
        for path in touched
        if path and not path.startswith("-")
    }


def _is_contract_path(path: str) -> bool:
    return path.startswith(_CLOSURE_CONTRACT_PREFIX) and path.endswith(".json")


def _repository_file_path(root: Path, declaration: str) -> str | None:
    """Return one in-root Git path, dropping an optional pytest selector."""
    file_path = declaration.split("::", 1)[0].replace("\\", "/").removeprefix("./")
    candidate = Path(file_path)
    if not file_path or candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        resolved_root = root.resolve(strict=True)
        resolved_file = (root / candidate).resolve(strict=True)
    except OSError:
        return None
    if not resolved_file.is_relative_to(resolved_root) or not resolved_file.is_file():
        return None
    return candidate.as_posix()


def _closure_authority_expected_red(
    touched: list[str], root: Path
) -> list[tuple[str, str]]:
    """Return ``(Git path, declared locator)`` pairs exempt in this C index.

    C publishes a deliberately RED oracle while all EXTEND targets already
    exist, a state that the ordinary missing-target expected-red law must not
    classify.  This narrower exception is available only to the constructor's
    private index and one touched, readable RED_TO_GREEN contract.  No normal
    ``.git/index`` commit can enter this branch.
    """
    index = os.environ.get("GIT_INDEX_FILE", "")
    if not index or _CLOSURE_INDEX.fullmatch(Path(index).name) is None:
        return []
    touched_paths = _touched_relative_paths(touched)
    contract_paths = sorted(path for path in touched_paths if _is_contract_path(path))
    if len(contract_paths) != 1:
        return []
    contract_path = root / contract_paths[0]
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if (
        not isinstance(contract, dict)
        or contract.get("delivery-route") != "RED_TO_GREEN"
    ):
        return []
    targets = contract.get("targets")
    if not isinstance(targets, dict) or not targets:
        return []
    for target_path, target in targets.items():
        if (
            not isinstance(target_path, str)
            or "::" in target_path
            or not isinstance(target, dict)
            or target.get("decision") != "EXTEND"
            or _repository_file_path(root, target_path) is None
        ):
            return []
    acceptance = contract.get("acceptance-tests")
    if not isinstance(acceptance, dict):
        return []
    locator = acceptance.get("locator")
    has_supporting = "supporting-locators" in acceptance
    supporting = acceptance.get("supporting-locators", [])
    try:
        current_schema_version = delivery_contract_schema_version()
    except RuntimeError:
        return []
    if (
        not isinstance(locator, str)
        or not locator
        or (has_supporting and contract.get("schema-version") != current_schema_version)
        or (
            not has_supporting
            and contract.get("schema-version") != LEGACY_SCHEMA_VERSION
        )
        or not isinstance(supporting, list)
        or (
            has_supporting
            and (
                not supporting
                or not all(
                    isinstance(path, str) and path and "::" not in path
                    for path in supporting
                )
            )
        )
    ):
        return []
    declared = [locator, *supporting]
    normalized = [_repository_file_path(root, path) for path in declared]
    if any(path is None for path in normalized) or len(set(normalized)) != len(
        normalized
    ):
        return []
    # Exact membership is intentional: a contract cannot make an unrelated
    # selected test disappear merely by naming it in authority bytes.
    return [
        (path, declaration)
        for declaration, path in zip(declared, normalized, strict=True)
        if path in touched_paths
    ]


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


def expected_red_reason(
    rel_path: str,
    declared: dict[str, tuple[str, set[str]]],
    collect: Callable[[str], tuple[int, str]],
) -> str | None:
    """The declared reason this file is red, or ``None`` -- meaning RUN IT.

    This is the OBSERVING half; the RULE is `des.domain.declared_red_oracles`,
    shared verbatim with `tests/conftest.py`. Collectibility is measured, never
    inferred (GDP-8, decide on the PROPERTY): an oracle that COLLECTS must run,
    and if it is red it blocks -- a declared oracle red for an UNDECLARED
    reason is a defect like any other.
    """
    if rel_path not in declared:
        return None
    returncode, output = collect(rel_path)
    if returncode == 0:
        return None  # it COLLECTS: it must run, and a red result stands as red
    return _declared_reason(rel_path, output, declared)


def partition_expected_red(
    runnable: list[str], root: Path, collect: Callable[[str], tuple[int, str]]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Split into (files that must RUN, files whose RED the contract declared)."""
    declared = declared_red_oracles(root)
    if not declared:
        return runnable, []
    keep: list[str] = []
    expected_red: list[tuple[str, str]] = []
    for rel_path in runnable:
        reason = expected_red_reason(rel_path, declared, collect)
        if reason is None:
            keep.append(rel_path)
        else:
            expected_red.append((rel_path, reason))
    return keep, expected_red


def _collect_only(root: Path, env: dict[str, str]) -> Callable[[str], tuple[int, str]]:
    """Observe collectibility for real. GDP-8: decide on the PROPERTY."""

    def run(rel_path: str) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                [
                    "uv",
                    "run",
                    "python3",
                    "-m",
                    "pytest",
                    rel_path,
                    "--collect-only",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                ],
                check=False,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (subprocess.TimeoutExpired, OSError):
            # Could not observe -> no declared reason -> the file RUNS. The
            # third state is never granted on an unmeasured property.
            return 1, ""
        return proc.returncode, proc.stdout + proc.stderr

    return run


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
    closure_expected_red = _closure_authority_expected_red(touched, root)
    if closure_expected_red:
        expected = {path for path, _declaration in closure_expected_red}
        runnable = [path for path in runnable if path not in expected]
        for path, declaration in closure_expected_red:
            print(
                f"{YELLOW}EXPECTED-RED CLOSURE AUTHORITY: {declaration} "
                f"(Git path: {path}){NC}",
                file=sys.stderr,
            )

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

    runnable, expected_red = partition_expected_red(
        runnable, root, _collect_only(root, env)
    )
    for rel_path, reason in expected_red:
        print(
            f"{YELLOW}EXPECTED-RED, not a failure: {rel_path}{NC}",
            file=sys.stderr,
        )
        print(f"{YELLOW}  {reason}{NC}", file=sys.stderr)

    if not runnable:
        print(
            f"{GREEN}Touched-file test gate: green "
            f"({len(expected_red)} declared expected-red oracle(s), nothing left "
            f"to run).{NC}"
        )
        return 0

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
