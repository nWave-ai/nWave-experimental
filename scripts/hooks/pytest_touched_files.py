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
pre-commit hands us the staged paths on argv (``pass_filenames: true``), so
selection never shells out to git. Opt-in evidence additionally records a
bounded, read-only observation of Git HEAD and worktree dirtiness; it does not
use Git to select tests or infer a reusable candidate identity.

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

DIAGNOSTIC MODE
---------------
``--diagnose`` is an explicit, caller-selected investigation of the affected
test-file scope. It reuses this selector, launches every selected *runnable*
file within the existing bounded ceiling, and disables pytest's early-stop
behaviour. It does not inherit ``PYTEST_ADDOPTS`` selection filters. Repository
pytest configuration still controls collection. It prints the complete argv
actually launched plus every deferred and uncovered path. That is evidence
about the selected files only; it is not a claim of whole-project or full-case
coverage. A selected run that collects zero tests is INCOMPLETE, never green.

The ordinary pre-commit invocation stays fail-fast and bounded by
``MAX_TEST_FILES_PER_COMMIT``; diagnostic scope above that ceiling is
INCOMPLETE and is not launched. ``--diagnose`` is intentionally not wired into
pre-commit: an LLM or developer chooses the related property x consumer scope
and the next command after reading the failures.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
from des.domain.repo_path_resolver import resolve_repo_root
from des.runtime.test_execution import run_pytest_reaped


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

TESTS_ROOT = "tests"
SOURCE_ROOTS = ("src/", "scripts/", "nwave_ai/")

EVIDENCE_DIR_ENV = "NWAVE_TOUCHED_FILES_EVIDENCE_DIR"

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
    return resolve_repo_root(None)


def _touched_relative_paths(touched: list[str]) -> set[str]:
    """Normalize the one Git spelling used by hook argv and contracts."""
    return {
        path.replace("\\", "/").removeprefix("./")
        for path in touched
        if path and not path.startswith("-")
    }


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


def module_names(rel_path: str) -> set[str]:
    """Dotted module spellings a Python source file could be imported as."""
    if not rel_path.endswith(".py"):
        return set()
    parts = rel_path[:-3].split("/")
    if parts[-1] == "__init__":
        return set()
    names = {".".join(parts)}
    if parts[0] == "src":
        names.add(".".join(parts[1:]))
    return {name for name in names if name.count(".") >= 1}


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


def _pytest_command(targets: list[str], *, diagnose: bool = False) -> list[str]:
    args = [*targets, "--tb=short", "-q"]
    if diagnose:
        # Command-line options follow PYTEST_ADDOPTS, so this explicit zero
        # overrides an ambient -x and lets the selected scope finish.
        args.append("--maxfail=0")
    else:
        args.append("-x")
    args.extend(["-p", "no:cacheprovider"])
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


def _print_scope(deferred: list[str], uncovered: list[str]) -> None:
    for entry in uncovered:
        print(f"{YELLOW}UNCOVERED: {entry}{NC}", file=sys.stderr)
    for path in deferred:
        print(f"{YELLOW}DEFERRED to pre-push/CI: {path}{NC}", file=sys.stderr)


def _print_command(command: list[str]) -> None:
    print(f"{BLUE}RUN: {shlex.join(command)}{NC}")


def _clear_git_environment() -> None:
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_AUTHOR_DATE",
    ):
        os.environ.pop(var, None)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _source_entry(root: Path, relative: str) -> dict[str, str | None]:
    """Return one file identity, preserving an explicit unknown on read failure."""
    try:
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    except FileNotFoundError:
        return {
            "path": relative,
            "sha256": None,
            "identity": "unknown",
            "reason": "path_missing_or_deleted",
        }
    except OSError:
        return {
            "path": relative,
            "sha256": None,
            "identity": "unknown",
            "reason": "path_unreadable",
        }
    return {"path": relative, "sha256": digest, "identity": "known", "reason": None}


def _source_snapshots(
    root: Path, paths: list[str], cache: dict[str, dict[str, str | None]] | None = None
) -> list[dict[str, str | None]]:
    """Capture each path at most once per snapshot, sharing values across scopes."""
    entries = cache if cache is not None else {}
    snapshots: list[dict[str, str | None]] = []
    for relative in paths:
        if relative not in entries:
            entries[relative] = _source_entry(root, relative)
        snapshots.append(entries[relative])
    return snapshots


def _git_observation(root: Path) -> dict[str, object]:
    """Capture only bounded, read-only Git facts; they never identify a candidate."""
    unknown_head: dict[str, str] = {
        "identity": "unknown",
        "reason": "git_head_unavailable_or_unborn",
    }
    unknown_dirty: dict[str, str] = {
        "identity": "unknown",
        "reason": "git_worktree_status_unavailable",
    }
    try:
        head = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(root),
                "rev-parse",
                "--verify",
                "HEAD",
            ],
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        head_fact: dict[str, str] = unknown_head
    else:
        value = head.stdout.strip()
        head_fact = (
            {"identity": "known", "value": value}
            if head.returncode == 0 and value
            else unknown_head
        )
    try:
        status = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        dirty_fact: dict[str, object] = unknown_dirty
    else:
        dirty_fact = (
            {"identity": "known", "value": bool(status.stdout.strip())}
            if status.returncode == 0
            else unknown_dirty
        )
    return {"head": head_fact, "worktree_dirty": dirty_fact}


def _declared_environment(env: dict[str, str]) -> dict[str, str]:
    return {name: env[name] for name in ("PYTHONPATH", "PYTEST_ADDOPTS") if name in env}


def _receipt(
    *,
    command: list[str],
    root: Path,
    selected_sources: list[dict[str, str | None]],
    declared_touched_inputs: list[dict[str, str | None]],
    git_observation: dict[str, object],
    env: dict[str, str],
    started: str,
    state: str,
    duration_seconds: float | None = None,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
    selected_sources_after: list[dict[str, str | None]] | None = None,
    declared_touched_inputs_after: list[dict[str, str | None]] | None = None,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_version": 2,
        "state": state,
        "started_at": started,
        "argv": command,
        "cwd": str(root),
        "selected_sources": selected_sources,
        "declared_touched_inputs": declared_touched_inputs,
        "candidate_identity": {
            "kind": "unknown",
            "reason": "observed_git_and_input_subset_cannot_identify_complete_executed_candidate",
            "observed_git": git_observation,
        },
        "receipt_scope": (
            "declared touched input paths and selected test files only; excludes "
            "transitive dependencies and the ambient environment; this receipt "
            "does not grant candidate reuse"
        ),
        "declared_environment": _declared_environment(env),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_seconds": duration_seconds,
    }
    if selected_sources_after is not None:
        receipt["selected_sources_after"] = selected_sources_after
        receipt["source_identity_drift"] = selected_sources_after != selected_sources
    if declared_touched_inputs_after is not None:
        receipt["declared_touched_inputs_after"] = declared_touched_inputs_after
        receipt["input_identity_drift"] = (
            declared_touched_inputs_after != declared_touched_inputs
        )
    return receipt


def _evidence_attempt() -> Path | None:
    raw = os.environ.get(EVIDENCE_DIR_ENV)
    if not raw:
        return None
    parent = Path(raw).expanduser()
    stamp = datetime.now(timezone.utc).strftime("attempt-%Y%m%dT%H%M%S%fZ")
    attempt = parent / f"{stamp}-{os.getpid()}"
    attempt.mkdir(parents=True, exist_ok=False)
    return attempt


def _print_captured(stdout: str | None, stderr: str | None) -> None:
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)


@contextmanager
def _evidence_stream(attempt: Path | None):
    if attempt is None:
        yield None
        return
    with (attempt / "stdout-stderr.txt").open("w+b") as stream:
        yield stream


def _run_selected(
    command: list[str], root: Path, env: dict[str, str], attempt: Path | None
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    with _evidence_stream(attempt) as stream:
        try:
            result = run_pytest_reaped(
                command,
                cwd=root,
                env=env,
                timeout=1800,
                capture_output=False,
                text=True,
                stdout=stream,
                stderr=stream,
            )
        except subprocess.TimeoutExpired as expired:
            if stream is None:
                raise
            stream.flush()
            stream.seek(0)
            partial = stream.read().decode(errors="replace")
            raise subprocess.TimeoutExpired(
                command, expired.timeout, output=partial, stderr=""
            ) from None
        if stream is None:
            return result, result.stdout or "", result.stderr or ""
        stream.flush()
        stream.seek(0)
        return result, stream.read().decode(errors="replace"), ""


def main(argv: list[str]) -> int:
    root = _repo_root()
    diagnose = "--diagnose" in argv
    unknown_options = [a for a in argv if a.startswith("-") and a != "--diagnose"]
    if unknown_options:
        print(
            f"{RED}Touched-file test gate: unknown option(s): "
            f"{' '.join(unknown_options)}.{NC}",
            file=sys.stderr,
        )
        return 2

    touched = [a for a in argv if a and not a.startswith("-")]
    if not touched:
        if diagnose:
            print(
                f"{YELLOW}DIAGNOSTIC INCOMPLETE: no affected files were selected; "
                f"no pytest run was launched.{NC}",
                file=sys.stderr,
            )
            return 1
        print(f"{GREEN}Touched-file test gate: nothing staged.{NC}")
        return 0

    runnable, deferred, uncovered = select(touched, root)
    if diagnose:
        _print_scope(deferred, uncovered)
    else:
        for entry in uncovered:
            print(f"{YELLOW}UNCOVERED at commit time: {entry}{NC}", file=sys.stderr)
    if deferred and not diagnose:
        print(
            f"{YELLOW}Deferred to pre-push/CI ({len(deferred)} file(s)): Docker/"
            f"multi-language tiers cost minutes each.{NC}",
            file=sys.stderr,
        )

    if not runnable:
        if diagnose:
            print(
                f"{YELLOW}DIAGNOSTIC INCOMPLETE: no runnable test files were "
                f"selected; no pytest run was launched.{NC}",
                file=sys.stderr,
            )
            return 1
        print(
            f"{GREEN}Touched-file test gate: no test file impacted by this commit.{NC}"
        )
        return 0

    if len(runnable) > MAX_TEST_FILES_PER_COMMIT:
        # Box-safety valve, and it says so instead of truncating to an arbitrary
        # subset. Reached only by a near-root conftest.py: this box is 4 cores /
        # ~11GB and a suite-wide run at commit time is the exact memory
        # saturation that has OOM-corrupted .git here.
        if diagnose:
            print(
                f"{YELLOW}DIAGNOSTIC INCOMPLETE: {len(runnable)} runnable test "
                f"files are above the bounded ceiling of "
                f"{MAX_TEST_FILES_PER_COMMIT}; no pytest run was launched.{NC}",
                file=sys.stderr,
            )
            return 1
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

    if diagnose:
        print(
            f"{BLUE}Diagnostic touched-file scope: {len(runnable)} runnable test "
            f"file(s) will be launched without early stop; repository collection "
            f"rules still apply (not whole-project or full-case coverage).{NC}"
        )
    else:
        print(
            f"{BLUE}Touched-file test gate: {len(runnable)} test file(s) impacted.{NC}"
        )

    _clear_git_environment()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    if diagnose:
        # A caller's `-k`, `-m`, or `-x` must not silently narrow the requested
        # diagnostic files. Repository configuration remains visible in argv
        # behaviour and is named in the scope report above.
        env.pop("PYTEST_ADDOPTS", None)
    command = _pytest_command(runnable, diagnose=diagnose)
    if diagnose:
        _print_command(command)

    evidence_attempt = _evidence_attempt()
    evidence_path = evidence_attempt / "receipt.json" if evidence_attempt else None
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    declared_touched_paths = sorted(_touched_relative_paths(touched))
    initial_source_cache: dict[str, dict[str, str | None]] = {}
    declared_touched_inputs = (
        _source_snapshots(root, declared_touched_paths, initial_source_cache)
        if evidence_path
        else []
    )
    selected_sources = (
        _source_snapshots(root, runnable, initial_source_cache) if evidence_path else []
    )
    git_observation = _git_observation(root) if evidence_path else {}
    if evidence_path is not None:
        _atomic_json(
            evidence_path,
            _receipt(
                command=command,
                root=root,
                selected_sources=selected_sources,
                declared_touched_inputs=declared_touched_inputs,
                git_observation=git_observation,
                env=env,
                started=started_at,
                state="incomplete",
            ),
        )

    try:
        result, stdout, stderr = _run_selected(command, root, env, evidence_attempt)
    except subprocess.TimeoutExpired as expired:
        stdout = expired.output if isinstance(expired.output, str) else ""
        stderr = expired.stderr if isinstance(expired.stderr, str) else ""
        if evidence_path is not None:
            post_run_cache: dict[str, dict[str, str | None]] = {}
            _atomic_json(
                evidence_path,
                _receipt(
                    command=command,
                    root=root,
                    selected_sources=selected_sources,
                    declared_touched_inputs=declared_touched_inputs,
                    git_observation=git_observation,
                    env=env,
                    started=started_at,
                    state="timeout",
                    duration_seconds=time.monotonic() - started,
                    stdout=stdout,
                    stderr=stderr,
                    selected_sources_after=_source_snapshots(
                        root, runnable, post_run_cache
                    ),
                    declared_touched_inputs_after=_source_snapshots(
                        root, declared_touched_paths, post_run_cache
                    ),
                ),
            )
        _print_captured(stdout, stderr)
        print()
        print(
            f"{RED}COMMIT BLOCKED -- INDETERMINATE: the touched-file test run", end=""
        )
        print(f" exceeded its 1800s bound.{NC}")
        print("      A gate that cannot decide must not pass. Re-run the command")
        print("      printed above by hand to see where it hangs.")
        return 1

    _print_captured(stdout, stderr)
    if evidence_path is not None:
        post_run_cache = {}
        _atomic_json(
            evidence_path,
            _receipt(
                command=command,
                root=root,
                selected_sources=selected_sources,
                declared_touched_inputs=declared_touched_inputs,
                git_observation=git_observation,
                env=env,
                started=started_at,
                state="complete",
                duration_seconds=time.monotonic() - started,
                stdout=stdout,
                stderr=stderr,
                exit_code=result.returncode,
                selected_sources_after=_source_snapshots(
                    root, runnable, post_run_cache
                ),
                declared_touched_inputs_after=_source_snapshots(
                    root, declared_touched_paths, post_run_cache
                ),
            ),
        )
    if result.returncode == 0:
        if diagnose:
            if deferred or uncovered:
                print(
                    f"{YELLOW}DIAGNOSTIC INCOMPLETE: selected runnable test files "
                    f"passed, but deferred or uncovered paths remain outside the "
                    f"launched scope.{NC}",
                    file=sys.stderr,
                )
                return 1
            print(f"{GREEN}Diagnostic touched-file scope: green.{NC}")
        else:
            print(f"{GREEN}Touched-file test gate: green.{NC}")
        return 0

    if result.returncode == 5:
        if diagnose:
            print(
                f"{YELLOW}DIAGNOSTIC INCOMPLETE: pytest collected zero tests from "
                f"the launched selected scope.{NC}",
                file=sys.stderr,
            )
        else:
            print(
                f"{RED}COMMIT BLOCKED -- INCOMPLETE: pytest collected zero tests "
                f"from the selected scope.{NC}",
                file=sys.stderr,
            )
        return 1

    if not diagnose:
        print()
        print(
            f"{RED}COMMIT BLOCKED -- a test covering a file in this commit is RED.{NC}"
        )
        print()
        print(
            f"{RED}WHAT{NC}  pytest failed over the {len(runnable)} test file(s) that"
        )
        print("      reference the source files this commit touches (see the")
        print("      traceback above for the failing node).")
        print(
            f"{RED}WHY{NC}   Until 2026-08-23 the local gate selected 78 of 6548 tests"
        )
        print("      by MARKER, so a defect in a touched file met nothing before")
        print("      reaching the trunk. This gate selects by TOUCHED FILE instead.")
        print(f"{RED}HOW{NC}   Reproduce exactly what just ran:")
        _print_command(command)
        print("      Fix the code or the test, then commit again.")
        print("      If the failure is unrelated to this commit, it is still a red")
        print("      test in a file you touched -- repair on sight, do not bypass.")
        return 1

    print()
    print(
        f"{RED}DIAGNOSTIC RED -- one or more tests in the complete selected scope "
        f"failed.{NC}"
    )
    print(f"{RED}WHAT{NC}  pytest completed the selected runnable scope and returned ")
    print(f"      exit status {result.returncode}; inspect every failure above.")
    print(f"{RED}HOW{NC}   Re-run the exact command printed before the test output.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
