"""Regression: the `pytest-fast-gate` pre-commit lock is worktree-scoped.

Root cause (bugfix-precommit-flock-scoped, 2026-07-20): ``pytest-fast-gate``
wrapped its run in ``flock -w 1800 /tmp/nwave-pytest.lock`` — ONE lock file
shared across EVERY worktree on the box. Under swarm-parallel-delivery a
commit in worktree A blocked on the lock while worktree B's own commit
already held it; the CLI-tool-enforced timeout (~2min) fired long before the
1800s flock wait would, so the commit appeared to hang, forcing
``--no-verify`` as the only practical escape (observed directly, several
times, across concurrently-committing worktrees the same session).

Premise check (see docs/product/expectations/bugfix-precommit-flock-scoped/):
``pytest-fast-gate`` is a ~13s static source-level scan of the worktree's OWN
files (tests/meta/test_source_banned_patterns.py et al.) — it neither writes
shared state nor stresses box memory, so it has NO genuine cross-worktree
invariant to protect. The heavier tiers (``pytest-quick-tiers``,
``pytest-e2e``) DO have one (per-box OOM risk from `-n`-parallel runs,
documented in .pre-commit-config.yaml) and correctly remain on the shared
lock — this file pins that split, not a blanket "always scope" claim.

Fix: `pytest-fast-gate`'s lock path is now `.nwave/pytest-fast-gate.lock` —
relative to the invoking worktree's own checkout root (the CWD pre-commit
hooks run under). Since each worktree is a physically distinct directory,
this is unconditionally unique per worktree (no hash/derivation collision
risk), while two commits WITHIN the same worktree still resolve to the same
file and correctly serialize.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"

_HAS_FLOCK = __import__("shutil").which("flock") is not None
_SKIP_NO_FLOCK = pytest.mark.skipif(
    not _HAS_FLOCK,
    reason="flock not on PATH (CONTRIBUTING.md prerequisite absent on this host)",
)

# A short, deterministic sleep so the concurrency assertions have real margin
# without making the test slow. Not `sleep` (coreutils) to keep the
# subprocess Python-only, matching the interpreter-parity sibling test.
_SLEEP_PROGRAM = "import time; time.sleep({seconds})"


def _hook_entries() -> dict[str, str]:
    """Map hook id -> raw `entry:` string, for every local hook."""
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    entries: dict[str, str] = {}
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            hook_id = hook.get("id")
            entry = hook.get("entry")
            if hook_id and entry:
                entries[hook_id] = entry
    return entries


def _flock_lock_path(entry: str) -> str:
    """Extract the lock-file argument from a `flock -w <secs> <path> ...` entry."""
    tokens = shlex.split(entry)
    assert tokens[0] == "flock", f"entry does not start with flock: {entry!r}"
    assert tokens[1] == "-w", f"expected -w wait flag, got: {tokens[1]!r} in {entry!r}"
    return tokens[3]


def _run_locked(cwd: Path, lock_relpath: str, sleep_seconds: float) -> subprocess.Popen:
    """Start (not wait) a `flock <lock_relpath> python3 -c sleep(...)` under cwd."""
    return subprocess.Popen(
        [
            "flock",
            "-w",
            "10",
            lock_relpath,
            sys.executable,
            "-c",
            _SLEEP_PROGRAM.format(seconds=sleep_seconds),
        ],
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Static config pins — the split documented above, mechanically enforced.
# ---------------------------------------------------------------------------


def test_fast_gate_lock_is_worktree_relative_not_global_tmp():
    """pytest-fast-gate's lock path must be relative (worktree-scoped), not /tmp."""
    entry = _hook_entries()["pytest-fast-gate"]
    lock_path = _flock_lock_path(entry)

    assert not lock_path.startswith("/"), (
        f"pytest-fast-gate lock path {lock_path!r} is absolute — it must be "
        "relative to the worktree's own checkout root so it resolves to a "
        "different file per worktree (see bugfix-precommit-flock-scoped)."
    )
    assert "/tmp/" not in lock_path and not lock_path.startswith("tmp/"), (
        f"pytest-fast-gate lock path {lock_path!r} still points at a shared "
        "/tmp location — this is exactly the over-serialization bug."
    )


def test_heavier_tiers_keep_the_genuinely_global_lock():
    """pytest-quick-tiers and pytest-e2e must stay on the shared /tmp lock.

    Negative pin: this bugfix scopes ONLY pytest-fast-gate. The heavier tiers
    have a real per-box OOM invariant (documented in .pre-commit-config.yaml)
    and must not be silently scoped along with the fix above.
    """
    entries = _hook_entries()
    for hook_id in ("pytest-quick-tiers", "pytest-e2e"):
        lock_path = _flock_lock_path(entries[hook_id])
        assert lock_path == "/tmp/nwave-pytest.lock", (
            f"{hook_id} lock path changed to {lock_path!r} — this tier is a "
            "documented cross-worktree/box OOM invariant and must remain on "
            "the shared global lock."
        )


# ---------------------------------------------------------------------------
# Behavioral pins — drive the hook's actual lock-acquisition logic.
# ---------------------------------------------------------------------------


@_SKIP_NO_FLOCK
def test_two_worktrees_commit_concurrently_without_lock_contention(tmp_path):
    """Two DIFFERENT worktrees' fast-gate locks must not contend.

    Simulates two worktrees as two temp directories, each holding the SAME
    relative lock path pytest-fast-gate uses. Firing both concurrently must
    complete in ~1 sleep duration (parallel), not ~2 (serialized) — proving
    the fix removed the cross-worktree contention that caused commits to
    time out under swarm-parallel-delivery.
    """
    lock_relpath = _flock_lock_path(_hook_entries()["pytest-fast-gate"])

    worktree_a = tmp_path / "worktree-a"
    worktree_b = tmp_path / "worktree-b"
    (worktree_a / Path(lock_relpath).parent).mkdir(parents=True, exist_ok=True)
    (worktree_b / Path(lock_relpath).parent).mkdir(parents=True, exist_ok=True)

    sleep_seconds = 1.0
    start = time.monotonic()
    proc_a = _run_locked(worktree_a, lock_relpath, sleep_seconds)
    proc_b = _run_locked(worktree_b, lock_relpath, sleep_seconds)
    assert proc_a.wait(timeout=10) == 0
    assert proc_b.wait(timeout=10) == 0
    elapsed = time.monotonic() - start

    # Serialized would take ~2x sleep_seconds; parallel takes ~1x. Threshold
    # sits comfortably between the two, with margin for process-spawn noise.
    assert elapsed < sleep_seconds * 1.7, (
        f"two different worktrees contended on the fast-gate lock: took "
        f"{elapsed:.2f}s for two {sleep_seconds}s runs (expected ~{sleep_seconds:.2f}s "
        "if truly independent). The lock is not worktree-scoped."
    )


@_SKIP_NO_FLOCK
def test_same_worktree_commits_still_serialize(tmp_path):
    """Two commits in the SAME worktree must still serialize on the fast-gate lock.

    The fix must not accidentally remove same-worktree protection while
    fixing the cross-worktree over-serialization above.
    """
    lock_relpath = _flock_lock_path(_hook_entries()["pytest-fast-gate"])

    worktree = tmp_path / "worktree-solo"
    (worktree / Path(lock_relpath).parent).mkdir(parents=True, exist_ok=True)

    sleep_seconds = 0.8
    start = time.monotonic()
    proc_1 = _run_locked(worktree, lock_relpath, sleep_seconds)
    proc_2 = _run_locked(worktree, lock_relpath, sleep_seconds)
    assert proc_1.wait(timeout=10) == 0
    assert proc_2.wait(timeout=10) == 0
    elapsed = time.monotonic() - start

    # Two SAME-worktree runs must serialize: total time is ~2x one run.
    assert elapsed >= sleep_seconds * 1.7, (
        f"two commits in the SAME worktree raced instead of serializing: "
        f"took {elapsed:.2f}s for two {sleep_seconds}s runs (expected "
        f"~{2 * sleep_seconds:.2f}s if correctly serialized). Same-worktree "
        "protection regressed."
    )


@_SKIP_NO_FLOCK
def test_lock_path_resolution_is_unconditionally_unique_per_worktree(tmp_path):
    """Negative case from the charter oracle: derivation must not silently collide.

    A CWD-relative lock path resolves to a *different absolute file* for every
    distinct worktree directory by construction (no hashing/derivation step
    that could theoretically collide) — verify this directly rather than
    merely asserting the config string looks relative.
    """
    lock_relpath = _flock_lock_path(_hook_entries()["pytest-fast-gate"])

    worktree_a = tmp_path / "worktree-a"
    worktree_b = tmp_path / "worktree-b"
    worktree_a.mkdir()
    worktree_b.mkdir()

    resolved_a = (worktree_a / lock_relpath).resolve()
    resolved_b = (worktree_b / lock_relpath).resolve()

    assert resolved_a != resolved_b, (
        f"lock path {lock_relpath!r} resolved to the SAME absolute file for "
        f"two different worktree roots ({resolved_a} == {resolved_b}) — the "
        "per-worktree scoping is not actually unique."
    )
