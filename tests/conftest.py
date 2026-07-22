"""Root conftest.py for all tests - ensures test isolation."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from filelock import FileLock


# ---------------------------------------------------------------------------
# Project root (single source of truth for autouse fixtures below).
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent


# velocity-v2 (<5min goal G-143): memoize the real-repo whole-tree collect across the
# session (run_contract_gate honors NWAVE_COLLECT_MEMO; only the immutable real repo
# is cached — verified in tests/des/unit/cli/test_run_contract_gate_collect_memo.py).
# Set at the ROOT so every test directory shares one collection, not just
# tests/des/acceptance/.
os.environ.setdefault("NWAVE_COLLECT_MEMO", "1")


# ---------------------------------------------------------------------------
# Build-once-share: the project's dev wheel is IDENTICAL across the whole
# session (the source tree is immutable within a run), yet ~15 test sites each
# rebuild it from scratch (``python -m build --wheel`` ~20 s apiece). This
# session-scoped, xdist-safe fixture builds it EXACTLY ONCE and every consumer
# reuses the same artifact -- no test is hidden or excluded, only the redundant
# from-scratch rebuild is removed. First worker to reach the FileLock builds;
# the rest reuse the produced ``.whl``. No cross-run cache on purpose: a single
# per-run build is correct by construction and cannot go stale.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def shared_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the project dev wheel once per session, shared across xdist workers.

    Returns the path to the single built ``.whl``. Consumers must treat it as
    read-only (it is shared). Swap any local ``python -m build --wheel`` fixture
    to depend on this instead of rebuilding.
    """
    # ``getbasetemp().parent`` is the run-root shared by every xdist worker.
    shared_root = tmp_path_factory.getbasetemp().parent
    wheel_dir = shared_root / "shared_wheel"
    lock = shared_root / "shared_wheel.lock"
    with FileLock(str(lock)):
        existing = list(wheel_dir.glob("*.whl")) if wheel_dir.exists() else []
        if not existing:
            wheel_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300,
            )
            assert result.returncode == 0, (
                "shared wheel build failed:\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected 1 shared wheel, found {len(wheels)}: {wheels}"
    return wheels[0]


@pytest.fixture(scope="session")
def shared_wheel_venv(
    shared_wheel: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """A clean venv with the dev wheel installed, built ONCE per session (uv).

    Uses ``uv venv`` + ``uv pip install`` (≈10× faster than ``python -m venv`` +
    ``pip install`` for the ~137-package dependency closure) so the real
    install-and-smoke path stays genuine while the from-scratch install cost is
    paid once and shared. Read-only for consumers. Returns the venv dir.
    """
    shared_root = tmp_path_factory.getbasetemp().parent
    venv_dir = shared_root / "shared_wheel_venv"
    venv_python = venv_dir / "bin" / "python"
    lock = shared_root / "shared_wheel_venv.lock"
    with FileLock(str(lock)):
        if not venv_python.exists():
            create = subprocess.run(
                ["uv", "venv", str(venv_dir)],
                capture_output=True,
                text=True,
                timeout=180,
            )
            assert create.returncode == 0, (
                f"uv venv failed:\nstdout: {create.stdout}\nstderr: {create.stderr}"
            )
            install = subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(venv_python),
                    str(shared_wheel),
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            assert install.returncode == 0, (
                "uv pip install of shared wheel failed:\n"
                f"stdout: {install.stdout}\nstderr: {install.stderr}"
            )
    assert venv_python.exists(), f"shared wheel venv missing python: {venv_python}"
    return venv_dir


# ---------------------------------------------------------------------------
# Per-test `.nwave` ROOT isolation (DDD-15, slice-05 of sustainable-test-suite).
#
# PARALLELISM RESTORATION. Production `.nwave`-path lookups resolve their root via
# `des.domain.nwave_root.resolve_nwave_root`, which prefers a `DES_PROJECT_DIR`
# override over the shared `Path.cwd()`. Under `-n auto` xdist workers share the
# repo cwd, so a test that writes `.nwave` state via the cwd root contaminates a
# sibling worker's wave-aware read (the masked interference serial `-n0` hid).
#
# This autouse fixture gives EVERY test its own fresh per-test `.nwave` root: it
# sets `DES_PROJECT_DIR` to a unique tmp dir for the test's duration and restores
# the prior value on teardown (monkeypatch). STRICTLY ADDITIVE to the
# `_clean_wave_active_floor` guard below — it does NOT touch the real repo
# `.nwave`; it redirects the resolver away from it.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_nwave_root(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Root each test's `.nwave` state under a fresh per-test tmp dir.

    Sets ``DES_PROJECT_DIR`` to a unique tmp dir so ``resolve_nwave_root`` returns
    a per-test isolated root, never the shared repo ``Path.cwd()``. ``monkeypatch``
    restores the prior environment after the test, so the real-repo fallback path
    (and any subprocess that sets its own ``DES_PROJECT_DIR``) is untouched.
    """
    per_test_root = tmp_path_factory.mktemp("nwave_root")
    monkeypatch.setenv("DES_PROJECT_DIR", str(per_test_root))


# ---------------------------------------------------------------------------
# Per-test git-hooks-dir isolation (F-INSTALLER-TEST-POLLUTES-TRACKED-HOOKS).
#
# In-process installs (the installer/uninstaller acceptance fixtures and any
# plugin install) call `scripts.shared.git_hooks_paths.resolve_hooks_dir` with
# the real repo as cwd. That resolver runs `git rev-parse --git-common-dir` from
# cwd and takes NO target argument, so it resolves the REAL repo's hooks dir.
# When a fixture also mocks `subprocess.run` to empty stdout it degenerates to
# `Path("") / "hooks"` == `<repo>/hooks` -- a TRACKED path -- and the DES pre-push
# backstop overwrites the committed `hooks/pre-push` with a machine-specific
# `/tmp/pytest-...` shim. With a real subprocess it instead clobbers the
# developer's live `<repo>/.git/hooks/pre-push`. Either way an in-process install
# must never write the real repo's hook tree.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _isolate_git_hooks_dir(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """Redirect installer git-hooks resolution away from the real repo tree.

    Wraps ``resolve_hooks_dir`` so that whenever resolution would land inside the
    real repo tree it returns a throwaway session-tmp hooks dir instead; a test
    that has built (and chdir'd into) its own sandbox git repo resolves OUTSIDE
    the repo tree and is deferred to untouched. Patches BOTH installer-facing
    bindings: ``des_plugin`` re-imports the source module function-locally
    (covered by patching the source module), while ``attribution_utils`` holds a
    module-level binding copy. The unit test
    ``tests/installer/unit/shared/test_git_hooks_paths.py`` holds its own import
    binding and exercises the real function, so it is unaffected.

    SESSION-scoped (not function-scoped) because the polluting installs are
    driven by MODULE-scoped fixtures (``installer_result`` / ``uninstaller_result``)
    that pytest instantiates BEFORE any function-scoped autouse fixture -- a
    function-scoped patch would apply too late. Session scope also patches once
    per xdist worker process, covering ``-n auto`` runs.
    """
    from scripts.shared import git_hooks_paths as _ghp

    sandbox_hooks = tmp_path_factory.mktemp("git_hooks") / "hooks"
    original_resolve = _ghp.resolve_hooks_dir
    project_root = _PROJECT_ROOT.resolve()

    def _sandboxed_resolve_hooks_dir() -> Path:
        try:
            resolved = original_resolve().resolve()
        except Exception:
            return sandbox_hooks
        if resolved == project_root or project_root in resolved.parents:
            return sandbox_hooks
        return resolved

    mp = pytest.MonkeyPatch()
    mp.setattr(_ghp, "resolve_hooks_dir", _sandboxed_resolve_hooks_dir)
    try:
        import scripts.install.attribution_utils as _attr_utils

        mp.setattr(_attr_utils, "resolve_hooks_dir", _sandboxed_resolve_hooks_dir)
    except Exception:
        pass
    try:
        yield
    finally:
        mp.undo()


@pytest.fixture(autouse=True)
def restore_working_directory():
    """
    Automatically restore the working directory after each test.

    This fixture ensures that tests which change the working directory
    (e.g., using os.chdir()) don't affect subsequent tests.

    The working directory is restored to the project root, which is
    determined by finding the directory containing pytest.ini.
    """
    # Save original working directory
    original_cwd = os.getcwd()

    # Ensure we're in the project root (directory containing pytest.ini)
    os.chdir(_PROJECT_ROOT)

    yield

    # Restore original working directory after test
    os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Test-isolation guard: the real-repo wave-active floor.
#
# cwd=real-repo subprocess tests read the wave floor
# `.nwave/wave-active/active.json` off `Path.cwd()` (production
# `WaveActiveReader`/`pre_tool_use_handler`). A floor left in the real repo by
# the live dev/Claude session (a real `/nw-*` dispatch arms `{"wave": ...}`) —
# or in principle a leaked one — makes any wave-aware test lacking the matching
# marker trip `WAVE_MARKER_BYPASS` (exit 2) and FAIL order-dependently. The
# xdist `real_repo_scan` pin only prevents PARALLEL collision; under `-n0` it is
# inert, so the floor must be cleaned explicitly. Tests that need a floor seed
# their OWN under `tmp_path` (different path) — untouched here.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_wave_active_floor():
    """Each test runs with NO real-repo wave-active floor.

    Remove the floor before AND after every test. Deliberately does NOT
    snapshot-and-restore: under ``-n>1`` the workers share this one on-disk
    file, so a write-back would race (one worker restoring a floor another
    worker's wave-aware test then reads). Tests must run floorless; a live
    dev's floor is session state the next ``/nw-*`` dispatch re-arms.
    """
    floor = _PROJECT_ROOT / ".nwave" / "wave-active" / "active.json"
    floor.unlink(missing_ok=True)
    try:
        yield
    finally:
        floor.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test-isolation guard: PR-22 (bootstrap_dev + git-hook templates) sets
# `git config --global init.templateDir = ~/.nwave/git-template/` so any
# subsequent `git init` (including in test tmp repos) inherits the project's
# hook stages — gitlint then rejects ephemeral fixture commits (`init`,
# `pr head`, `seed`, etc.) for not being Conventional Commits.
#
# Symptom: every fixture that creates a tmp git repo and commits hits
# subprocess exit-1 in CI (passes locally only because dev machines may
# not have the template set yet).
#
# Mitigation: override `GIT_TEMPLATE_DIR` to an empty value for ALL test
# subprocess invocations. This overrides any `init.templateDir` config and
# makes `git init` skip the template copy. Production behaviour is
# untouched (the production install path runs outside pytest).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_git_template(monkeypatch):
    """Skip the user-global git template for every test's subprocess git calls."""
    monkeypatch.setenv("GIT_TEMPLATE_DIR", "")


# ---------------------------------------------------------------------------
# Test-isolation guard: scrub git's repository-override environment variables
# (RCA Branch C, pre-push hook repair 2026-06-11 — evidence:
# /tmp/rca-evidence/branch-c-gitdir-repro.txt).
#
# git(1) env-override semantics: when GIT_DIR / GIT_COMMON_DIR / GIT_WORK_TREE /
# GIT_INDEX_FILE / GIT_OBJECT_DIRECTORY are set, EVERY git subprocess targets
# the repository they name — repo discovery from cwd is bypassed entirely. On
# a linked worktree, git's pre-push hook runner exports an ABSOLUTE GIT_DIR
# into the hook environment; pytest (and its git-spawning fixtures) inherits
# it, so an un-scrubbed `git init` in a tmp_path repo silently operates on the
# REAL shared repository (empirically: flipped shared core.bare=true).
#
# Mirror of pre-commit's own `no_git_env` scrub. Session-scoped so the vars
# are gone before any fixture or test spawns git; per-call `env=` scrubs in
# the git-fixture helpers are belt-and-braces for direct invocation paths.
# ---------------------------------------------------------------------------

GIT_REPO_OVERRIDE_VARS = (
    "GIT_DIR",
    "GIT_COMMON_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
)


@pytest.fixture(scope="session", autouse=True)
def _scrub_git_repo_override_env():
    """Delete git repo-override env vars for the whole test session."""
    with pytest.MonkeyPatch.context() as mp:
        for var in GIT_REPO_OVERRIDE_VARS:
            mp.delenv(var, raising=False)
        yield


# ---------------------------------------------------------------------------
# Class B regression guard — editable install health check (RCA 2026-05-13).
#
# Symptom: subprocess-based tests fail with
# `ModuleNotFoundError: No module named 'nwave_ai'` when run from a sandboxed
# cwd, because Python's `sys.path` no longer contains `''` and the editable
# install .pth file is missing/corrupted. Catching this at session start
# gives a clear actionable message instead of dozens of identical cryptic
# failures across `tests/outcomes/acceptance/`, `tests/feature_delta/...`.
#
# RCA: docs/feature/fix-outcomes-acceptance/discuss/rca.md.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _verify_nwave_ai_subprocess_importable():
    """Fast-fail if nwave_ai cannot be imported from a clean-cwd subprocess."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import nwave_ai"],
        cwd="/tmp",
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        pytest.exit(
            "FATAL: nwave_ai not importable from a clean-cwd subprocess. "
            "Class B regression — editable install .pth missing or corrupted.\n"
            f"  python: {sys.executable}\n"
            f"  stderr: {result.stderr.strip()}\n"
            "Fix: `uv sync` (or run `nwave-doctor` if available).",
            returncode=1,
        )


# ---------------------------------------------------------------------------
# Layer 1 — repo-wide GIT_CEILING_DIRECTORIES (Fix 1 from RCA).
# Function-scoped so pytest-xdist workers each get their own env, and so the
# var is cleaned up after every test (no global env mutation).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _git_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop subprocess git from walking up into the host repo.

    Sets ``GIT_CEILING_DIRECTORIES`` to the parent of the project root for
    every test. If a subprocess git invocation has its cwd resolve above
    its tmp_path (race / inode reuse / chdir interaction), git will fail
    to find a parent ``.git`` instead of mutating the host repo.

    Pairs with ``_git_pollution_guard`` below: env stops the leak, the
    detective guard catches it if env is bypassed (some tests build their
    own subprocess env dict and inherit only ``os.environ`` selectively).
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(_PROJECT_ROOT.parent))


# ---------------------------------------------------------------------------
# Git hooks guard — prevents any test from corrupting .git/hooks/
# ---------------------------------------------------------------------------


def _snapshot_hooks_dir(hooks_dir: Path) -> dict[str, bytes]:
    """Return a filename -> full-bytes mapping for all files in hooks_dir.

    Returns an empty dict when the directory does not exist. Pure function.
    Content is captured in full (not hashed) so the guard can restore the
    pre-session state in teardown — detection alone leaves corruption
    between sessions and blocks manual commits.
    """
    if not hooks_dir.is_dir():
        return {}
    return {
        entry.name: entry.read_bytes()
        for entry in sorted(hooks_dir.iterdir())
        if entry.is_file()
    }


def _restore_hooks_dir(hooks_dir: Path, snapshot: dict[str, bytes]) -> None:
    """Restore hooks_dir to match the captured snapshot exactly.

    Writes every file in the snapshot back to disk with its pre-session
    content + 0o755 permissions (hooks must be executable). Deletes any
    files that appeared during the session (and are not in the snapshot).
    Idempotent: calling twice with the same snapshot is a no-op.

    Gated by ``_common_git_dir_is_shared``: when the common ``.git`` is shared
    with live linked worktrees, the destructive restore is SKIPPED (WARN-ONLY)
    — a sibling worktree's hooks live in this same dir and must not be
    clobbered.
    """
    if not hooks_dir.is_dir():
        return
    if _common_git_dir_is_shared(hooks_dir.parent):
        _warn_shared_common_dir_restore_skipped(
            "hooks", sorted(snapshot), hooks_dir.parent
        )
        return
    current_names = {entry.name for entry in hooks_dir.iterdir() if entry.is_file()}
    # Delete files that appeared during the session
    for name in current_names - set(snapshot):
        (hooks_dir / name).unlink(missing_ok=True)
    # Restore original content for everything that was in the snapshot
    for name, content in snapshot.items():
        path = hooks_dir / name
        path.write_bytes(content)
        path.chmod(0o755)


def _locate_git_hooks_dir() -> Path:
    """Resolve the real .git/hooks directory, following worktree indirection.

    For a normal clone: <project_root>/.git/hooks/
    For a worktree:    the common .git/hooks/ of the main worktree.
    """
    project_root = Path(__file__).parent.parent
    git_path = project_root / ".git"
    if git_path.is_dir():
        return git_path / "hooks"
    # Worktree: .git is a file containing "gitdir: <path>"
    gitdir_line = git_path.read_text().strip()
    if gitdir_line.startswith("gitdir:"):
        worktree_git = Path(gitdir_line[len("gitdir:") :].strip())
        # Walk up to the common dir (two levels up from worktrees/<name>)
        common_git = worktree_git.parent.parent
        return common_git / "hooks"
    return git_path / "hooks"


@pytest.fixture(scope="session", autouse=True)
def guard_git_hooks():
    """Session-scoped guard that RESTORES and fails if tests corrupt .git/hooks/.

    Definitive fix for hook corruption: detection alone is insufficient —
    corrupted state survives the pytest session and blocks manual commits
    (e.g. plugin-installer tests calling install_attribution_hook without
    proper isolation can overwrite prepare-commit-msg). This fixture:

    1. Snapshots the hooks directory BEFORE the session (full bytes + perms).
    2. YIELDS — tests run and may corrupt hooks.
    3. UNCONDITIONALLY RESTORES the pre-session state in teardown,
       regardless of whether violations were detected.
    4. Computes the diff AFTER restore and fails loudly if any test
       touched the hooks directory, so the regression is still visible
       in CI/local output.

    Restore runs before the fail assertion so even a failing session
    leaves the hooks dir clean for the next commit attempt.
    """
    hooks_dir = _locate_git_hooks_dir()
    before = _snapshot_hooks_dir(hooks_dir)

    yield

    after = _snapshot_hooks_dir(hooks_dir)

    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(
        name for name in set(before) & set(after) if before[name] != after[name]
    )

    violations: list[str] = []
    if created:
        violations.append(f"Created: {created}")
    if deleted:
        violations.append(f"Deleted: {deleted}")
    if modified:
        violations.append(f"Modified: {modified}")

    if not violations:
        return

    if _common_git_dir_is_shared(hooks_dir.parent):
        # Shared common .git: sibling worktrees' hooks live in this same dir;
        # a restore would clobber them. Degrade to WARN-ONLY — never touch the
        # shared dir. (Guard already warns; no restore is performed.)
        _warn_shared_common_dir_restore_skipped(
            "hooks", "; ".join(violations), hooks_dir.parent
        )
        return

    # Exclusive common dir — unchanged single-writer behavior: UNCONDITIONAL
    # RESTORE first so the next commit is never blocked by leftover
    # corruption, then surface a warning (not a teardown failure — we want the
    # hooks left intact, not pre-commit runs blocked).
    _restore_hooks_dir(hooks_dir, before)

    import sys as _sys

    _sys.stderr.write(
        "\nHOOK-GUARD: test session corrupted .git/hooks/ — "
        + "; ".join(violations)
        + f"\n  hooks dir: {hooks_dir}"
        + "\n  (hooks dir has been RESTORED to the pre-session snapshot)\n"
    )


# ---------------------------------------------------------------------------
# Layer 2 — Detective guard: snapshot+diff+restore .git/{config,HEAD,refs/}.
#
# Two pure helpers form the API contract that tests/test_guard_fixtures.py
# locks (Step 01-01): _compute_git_state_snapshot and _diff_git_state. The
# autouse fixture _git_pollution_guard wraps them.
#
# Unlike `guard_git_hooks` (which warns), this fixture uses pytest.fail()
# because config/HEAD/refs corruption — unlike hooks corruption — is
# immediately repo-breaking and must halt the suite.
# ---------------------------------------------------------------------------


def _resolve_git_common_dir(project_root: Path) -> Path:
    """Resolve the git common dir, following worktree indirection.

    For a normal clone: ``<project_root>/.git`` (a directory).
    For a worktree: ``<project_root>/.git`` is a file containing
    ``gitdir: <path>/<common>/worktrees/<name>``; the common dir is two
    levels up.

    Pure: only reads filesystem state. No subprocess (deliberate — the
    guard runs per-test in worker scope; a `git rev-parse` would itself
    walk up and could trigger the very corruption we are trying to detect
    on a misconfigured repo).
    """
    git_path = project_root / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        gitdir_line = git_path.read_text().strip()
        if gitdir_line.startswith("gitdir:"):
            worktree_git = Path(gitdir_line[len("gitdir:") :].strip())
            # <common>/worktrees/<name> -> <common>
            return worktree_git.parent.parent
    return git_path


def _common_git_dir_is_shared(common_dir: Path) -> bool:
    """True when ``common_dir`` is shared with live linked worktrees.

    A git common dir gains a ``worktrees/`` subdirectory the moment a linked
    worktree is created; each live linked worktree owns one
    ``worktrees/<name>/`` entry. The signal is symmetric: resolved from the
    MAIN worktree its linked children appear there; resolved from a LINKED
    worktree its own entry appears there. A standalone clone with no linked
    worktrees has no ``worktrees/`` dir (or an empty one) and is therefore
    exclusively owned by this process.

    Pure filesystem, NO ``git`` subprocess — same discipline as
    ``_resolve_git_common_dir`` (the guard runs per-test in worker scope and
    must not shell out) and the Python-only / tool-agnostic gate mandate.

    Biased toward reporting SHARED: a stale ``worktrees/<name>`` entry left by
    a not-yet-pruned removed worktree reports shared, which only ever makes the
    caller REFRAIN from a destructive restore — the safe direction. The
    dangerous error (reporting exclusive while actually shared, then clobbering
    a sibling worktree's refs) never arises from a stale entry.

    Motivation: the detective guards below restore ``.git`` state by DIRECT
    file write on the common dir, assuming they are its sole writer. Under the
    swarm-parallel-delivery methodology many linked worktrees share one common
    ``.git``; a restore would then clobber a sibling's legitimate new branch /
    HEAD / config move (no reflog entry). This detector gates the destructive
    restore so it degrades to WARN-ONLY when shared.
    """
    worktrees_dir = common_dir / "worktrees"
    if not worktrees_dir.is_dir():
        return False
    return any(child.is_dir() for child in worktrees_dir.iterdir())


def _warn_shared_common_dir_restore_skipped(
    artifacts: str, diff: object, common_dir: Path
) -> None:
    """Emit a WHAT/WHY/HOW warning when a guard skips a destructive restore
    because the common ``.git`` is shared with live linked worktrees."""
    import sys as _sys

    _sys.stderr.write(
        f"\nGUARD (shared .git): {artifacts} change detected ({diff!r}) but "
        "the common git dir is shared with live linked worktrees — "
        "destructive restore SKIPPED.\n"
        f"  common dir: {common_dir}\n"
        "  WHAT: the detective guard saw a diff in the shared common .git.\n"
        "  WHY : under multi-worktree parallel delivery another live worktree's "
        "legitimate change (new branch, HEAD/config move) is indistinguishable "
        "from this test's pollution; a direct-file restore would silently "
        "clobber that sibling's work (no reflog entry).\n"
        "  HOW : degraded to WARN-ONLY. If THIS test truly mutates git state, "
        "isolate it into a throwaway repo under tmp_path "
        "(GIT_CEILING_DIRECTORIES) so the guard can safely restore. Restore "
        "re-enables automatically once the common dir is exclusively owned.\n"
    )


def _resolve_head_path(project_root: Path) -> Path:
    """Return the path to the HEAD that this worktree owns.

    Normal clone: ``<common>/HEAD``.
    Worktree: ``<common>/worktrees/<name>/HEAD`` (per-worktree HEAD).
    """
    git_path = project_root / ".git"
    if git_path.is_dir():
        return git_path / "HEAD"
    if git_path.is_file():
        gitdir_line = git_path.read_text().strip()
        if gitdir_line.startswith("gitdir:"):
            return Path(gitdir_line[len("gitdir:") :].strip()) / "HEAD"
    return git_path / "HEAD"


def _read_packed_refs(common_dir: Path) -> dict[str, str]:
    """Parse ``<common_dir>/packed-refs`` into a ``{ref_name: sha}`` map.

    Pure function. Returns ``{}`` if the file does not exist or is empty —
    a freshly-initialised repo has no packed-refs file at all, and a repo
    with all refs unpacked has only loose files.

    File format (``man git-pack-refs``)::

        # pack-refs with: peeled fully-peeled sorted
        <sha> <ref-name>
        ^<peeled-sha>            (annotation for the previous annotated tag)

    Comment lines (start with ``#``) and peeled-tag annotation lines
    (start with ``^``) are skipped — they are not refs themselves.

    Used by ``_compute_git_state_snapshot`` to distinguish
    routine-housekeeping promotions (loose ref appears with same SHA as
    an existing packed entry — ignore) from genuine ref creation (loose
    ref appears with a SHA never seen in packed-refs — flag).
    """
    packed_path = common_dir / "packed-refs"
    if not packed_path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in packed_path.read_text().splitlines():
        if not line or line.startswith("#") or line.startswith("^"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        sha, name = parts
        result[name.strip()] = sha.strip()
    return result


def _resolve_head_target(head_path: Path, common_dir: Path) -> bytes | None:
    """Return the SHA HEAD currently resolves to, or the raw HEAD bytes.

    Pure function. Reads ``HEAD`` directly; if it is a symbolic ref of the
    shape ``ref: refs/heads/<branch>\\n``, follows the pointer once to the
    target ref file and returns its bytes (the commit SHA). For detached
    HEAD (raw 40-char SHA in the file) returns the file bytes directly.

    When the symbolic-ref target has no loose file (``git pack-refs --all``
    deleted it), falls back to the SHA in ``packed-refs``. Only when both
    are absent (unborn branch, freshly-cloned bare ref) does it return the
    literal HEAD bytes — which would otherwise spuriously diff as ``HEAD``
    on a packed-only repo. Returns ``None`` if HEAD is absent.

    The reason we resolve the target rather than only snapshot the HEAD
    file: ``git commit`` does NOT touch HEAD when on a branch — it
    mutates ``refs/heads/<branch>``. The user-visible "HEAD moved"
    symptom of the RCA Branch A pollution therefore manifests as a
    change in the resolved target, not in HEAD's symbolic-ref text.
    Snapshotting only the literal bytes would miss that exact failure.
    """
    if not head_path.is_file():
        return None
    raw = head_path.read_bytes()
    text = raw.decode("utf-8", errors="replace").strip()
    if text.startswith("ref:"):
        ref_name = text[len("ref:") :].strip()
        target = common_dir / ref_name
        if target.is_file():
            return target.read_bytes()
        # Loose file absent — try packed-refs (housekeeping after pack).
        packed = _read_packed_refs(common_dir)
        packed_sha = packed.get(ref_name)
        if packed_sha is not None:
            # Match git's loose-ref on-disk shape: 40 hex + LF.
            return (packed_sha + "\n").encode("ascii")
    return raw


def _compute_git_state_snapshot(project_root: Path) -> dict[str, object]:
    """Return a byte-level snapshot of the load-bearing host git state.

    Pure function. The snapshot covers the four artifacts whose mutation
    constitutes pollution: ``config`` (shared across worktrees),
    ``HEAD`` (per-worktree), the union of loose ``refs/heads/`` and
    ``refs/tags/``, and the ``packed-refs`` map.

    Returns a dict with the contract:
        {
            "config":       <bytes | None>,      # raw .git/config bytes
            "HEAD_raw":     <bytes | None>,      # literal HEAD file bytes
            "HEAD_resolved":<bytes | None>,      # SHA target of HEAD, or
                                                 #   the raw bytes if HEAD
                                                 #   is detached / target
                                                 #   ref missing
            "refs":         <list[(str, bytes)]> # sorted (refname, sha-bytes)
            "packed_refs":  <dict[str, str]>     # ref_name -> sha hex map
        }

    Two HEAD fields exist by design (adversarial review D1 fix):
    ``HEAD_raw`` is what restore writes back so a symbolic-ref HEAD
    (``ref: refs/heads/<branch>\\n``) is preserved across restores —
    writing the resolved SHA would leave the worktree in detached-HEAD
    state. ``HEAD_resolved`` is what diff compares so ``git commit``
    (which only mutates ``refs/heads/<branch>``, not HEAD itself) is
    detected as a corruption: the resolved target advances even though
    HEAD's literal bytes are unchanged.

    The ``packed_refs`` field exists by design (Step 01-02 fix for the
    residual-RCA false-positive). It lets ``_diff_git_state`` distinguish
    routine git housekeeping (a packed ref gets promoted to a loose file
    with the same SHA — ignore) from genuine pollution (a brand-new ref
    appears with a SHA never seen in packed-refs — flag).

    Designed for ``_diff_git_state`` (returns subset of {"config","HEAD","refs"}
    naming what changed). Worktree gitdir indirection is resolved via
    ``_resolve_git_common_dir`` and ``_resolve_head_path``.

    Returns ``None`` for missing files instead of raising — a non-existent
    repo is still a deterministic state to diff against.
    """
    common_dir = _resolve_git_common_dir(project_root)
    config_path = common_dir / "config"
    head_path = _resolve_head_path(project_root)

    config_bytes = config_path.read_bytes() if config_path.is_file() else None

    # HEAD_raw: literal file bytes — used by restore to preserve the
    # symbolic-ref form (`ref: refs/heads/<branch>\n`).
    head_raw = head_path.read_bytes() if head_path.is_file() else None

    # HEAD_resolved: target SHA via _resolve_head_target. Used by diff so
    # `git commit` (which advances refs/heads/<branch> but leaves HEAD's
    # literal bytes unchanged) is detected as a HEAD corruption — that IS
    # the user-visible symptom of the RCA Branch A pollution.
    head_resolved = _resolve_head_target(head_path, common_dir)

    # refs: glob refs/heads/* and refs/tags/* under the common dir.
    refs: list[tuple[str, bytes]] = []
    for category in ("heads", "tags"):
        refs_dir = common_dir / "refs" / category
        if not refs_dir.is_dir():
            continue
        for ref_file in sorted(refs_dir.rglob("*")):
            if not ref_file.is_file():
                continue
            ref_name = f"refs/{category}/" + str(
                ref_file.relative_to(refs_dir)
            ).replace(os.sep, "/")
            refs.append((ref_name, ref_file.read_bytes()))

    return {
        "config": config_bytes,
        "HEAD_raw": head_raw,
        "HEAD_resolved": head_resolved,
        "refs": sorted(refs),
        "packed_refs": _read_packed_refs(common_dir),
        "project_root": project_root,
    }


def _is_descendant_ref_advance(
    project_root: object, before_sha: str, after_sha: str
) -> bool:
    """True iff ``after_sha`` is a git-descendant of ``before_sha``.

    Bugfix ``fix-git-pollution-guard-clobbers-concurrent-writer``: a loose
    ref that moved to a descendant commit is a LEGITIMATE external advance
    (e.g. the orchestrator committing on the branch while a guarded test
    session runs) — not corruption. Uses read-only
    ``git merge-base --is-ancestor``, scoped to ``project_root`` via
    ``GIT_CEILING_DIRECTORIES`` so it can never walk outside the target
    repo. Never invokes a mutating git command — this is a detection-only
    helper, unlike the restore path which is deliberately subprocess-free.

    Fail-closed on any undeterminable ancestry: identical SHAs count as
    "descendant" (no-op move); a non-zero/non-one exit code (unknown SHA,
    unborn ancestry, missing ``git`` binary, non-``Path`` project_root)
    returns ``False`` so the caller keeps flagging it as pollution.
    """
    if before_sha == after_sha:
        return True
    if not isinstance(project_root, Path):
        return False
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(project_root.parent)}
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "merge-base",
                "--is-ancestor",
                before_sha,
                after_sha,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _refs_diff_is_pollution(
    before_refs: list[tuple[str, bytes]],
    after_refs: list[tuple[str, bytes]],
    before_packed: dict[str, str],
    project_root: object = None,
) -> bool:
    """Return True iff the loose-refs change is real pollution.

    Pure except for case 3's ancestry check. Decomposes the previous
    all-or-nothing list-compare into three independent questions:

    1. New loose ref in ``after`` that was not in ``before``: is its SHA
       already in ``before``'s ``packed-refs``? If yes -> housekeeping
       promotion (ignore). If no -> creation (pollution).
    2. Loose ref in ``before`` that disappeared in ``after``: was its SHA
       in ``before``'s ``packed-refs``? If yes -> the ref was collapsed
       back into pack (housekeeping; ignore). If no -> deletion
       (pollution).
    3. SHA changed for a ref that exists in both ``before`` and ``after``:
       pollution UNLESS the new SHA is a git-descendant of the old one
       (``_is_descendant_ref_advance``) — a legitimate concurrent writer's
       advance, per the fix-git-pollution-guard-clobbers-concurrent-writer
       feature-delta. Non-descendant moves and undeterminable ancestry
       (``project_root`` absent/not a ``Path``, unknown SHA) stay
       fail-closed as pollution — unchanged from today's behavior.
    """
    before_map = dict(before_refs)
    after_map = dict(after_refs)

    # 1. Created loose refs.
    for name, sha_bytes in after_map.items():
        if name in before_map:
            continue
        sha = sha_bytes.decode("ascii", errors="replace").strip()
        if before_packed.get(name) == sha:
            continue  # promotion — housekeeping, ignore.
        return True  # genuine creation — pollution.

    # 2. Disappeared loose refs.
    for name, sha_bytes in before_map.items():
        if name in after_map:
            continue
        sha = sha_bytes.decode("ascii", errors="replace").strip()
        if before_packed.get(name) == sha:
            continue  # collapsed back into pack — housekeeping, ignore.
        return True  # genuine deletion — pollution.

    # 3. SHA changed on existing loose ref.
    for name, sha_bytes in after_map.items():
        if name not in before_map or before_map[name] == sha_bytes:
            continue
        before_sha = before_map[name].decode("ascii", errors="replace").strip()
        after_sha = sha_bytes.decode("ascii", errors="replace").strip()
        if _is_descendant_ref_advance(project_root, before_sha, after_sha):
            continue  # legitimate concurrent writer advance — ignore.
        return True

    return False


def _diff_git_state(before: dict[str, object], after: dict[str, object]) -> list[str]:
    """Return subset of {"config", "HEAD", "refs"} listing what changed.

    Pure function. Empty list = no corruption. Used by the autouse guard
    to drive ``pytest.fail()`` with a precise corruption-type list, and
    by ``tests/test_guard_fixtures.py`` to verify the predicate detects
    the exact failure modes of the 2026-04-27 incident.

    Refs comparison is promotion-aware (Step 01-02 fix): a new loose ref
    whose SHA already lives in ``before["packed_refs"]`` is housekeeping
    (the ref was promoted from pack to loose by ``git fetch`` / etc.) and
    must NOT be flagged. A new loose ref whose SHA is NOT in the packed
    map IS pollution — the legitimate-creation contract from
    ``test_guard_detects_refs_corruption`` is preserved.

    Symmetric in argument order modulo set semantics for config/HEAD; the
    refs branch is asymmetric by design (the ``before`` packed-refs map
    is the housekeeping witness, not the ``after`` one).
    """
    diff: list[str] = []
    if before.get("config") != after.get("config"):
        diff.append("config")
    # Compare HEAD_resolved (the SHA target) so `git commit` — which only
    # advances refs/heads/<branch> while leaving HEAD's literal bytes
    # unchanged — is still flagged. Adversarial review D1: HEAD_raw is the
    # restore field; HEAD_resolved is the diff field. Same ancestry
    # exemption as the refs seam (fix-git-pollution-guard-clobbers-
    # concurrent-writer): a descendant advance — a legitimate concurrent
    # writer's commit on the checked-out branch — is not corruption.
    # Non-descendant moves, undeterminable ancestry, and non-bytes values
    # stay fail-closed exactly as before.
    before_head = before.get("HEAD_resolved")
    after_head = after.get("HEAD_resolved")
    if before_head != after_head and not (
        isinstance(before_head, bytes)
        and isinstance(after_head, bytes)
        and _is_descendant_ref_advance(
            before.get("project_root"),
            before_head.decode("ascii", errors="replace").strip(),
            after_head.decode("ascii", errors="replace").strip(),
        )
    ):
        diff.append("HEAD")

    before_refs_obj = before.get("refs")
    after_refs_obj = after.get("refs")
    before_packed_obj = before.get("packed_refs")
    before_project_root = before.get("project_root")
    if (
        isinstance(before_refs_obj, list)
        and isinstance(after_refs_obj, list)
        and isinstance(before_packed_obj, dict)
    ):
        if _refs_diff_is_pollution(
            before_refs_obj, after_refs_obj, before_packed_obj, before_project_root
        ):
            diff.append("refs")
    elif before_refs_obj != after_refs_obj:
        # Fallback for snapshots produced before packed_refs was added —
        # preserve the old whole-list comparison so legacy callers still
        # see refs corruption.
        diff.append("refs")
    return diff


# Recursion-safety flag: while we are mid-restore, the guard MUST NOT
# re-enter (e.g. if a finalizer somehow re-invokes the snapshot path).
_GUARD_RESTORE_IN_PROGRESS = False


def _atomic_restore_git_state(project_root: Path, before: dict[str, object]) -> None:
    """Restore .git/{config,HEAD,refs/heads,refs/tags} from a snapshot.

    Direct file writes only — never invokes ``git`` as a subprocess
    because that is the exact escape vector this guard exists to defend
    against. Idempotent: calling twice with the same snapshot is a no-op.

    HEAD restore uses ``HEAD_raw`` (literal file bytes), NOT
    ``HEAD_resolved`` (the SHA target). Writing the SHA back would leave
    the worktree in detached-HEAD state — the original HEAD contained
    ``ref: refs/heads/<branch>\\n`` (a symbolic ref), and that text must
    be preserved verbatim. Adversarial review D1.

    Refs restore performs TWO passes (adversarial review D2): first
    writes back snapshot-before entries, then deletes any refs that
    appeared during the test (i.e. files under refs/heads or refs/tags
    that are not in ``refs_before``). Mirrors ``_restore_hooks_dir``'s
    pattern (lines 96-99). Detection alone is insufficient when the
    autouse guard wants the next test to start from a CLEAN snapshot —
    leftover refs would themselves be picked up as a corruption signal
    on the very next test, masking the true offender.

    Pass 2 is promotion-aware (Step 01-02): a loose ref absent from
    ``refs_before`` whose SHA matches an entry in
    ``before["packed_refs"]`` is left in place. It was promoted from
    pack to loose by routine git housekeeping (``git fetch``, etc.) —
    deleting it would destroy a legitimate ref the user owns.

    Sets the recursion flag so any concurrent guard invocation skips its
    snapshot phase while the restore is in flight.
    """
    global _GUARD_RESTORE_IN_PROGRESS
    _GUARD_RESTORE_IN_PROGRESS = True
    try:
        common_dir = _resolve_git_common_dir(project_root)
        if _common_git_dir_is_shared(common_dir):
            # Shared common .git: a sibling worktree's legitimate change is
            # indistinguishable from pollution; a direct-file restore would
            # clobber it. Degrade to WARN-ONLY. Detection stays; only the
            # destructive action is gated.
            _warn_shared_common_dir_restore_skipped(
                "config/HEAD/refs", None, common_dir
            )
            return
        config_path = common_dir / "config"
        head_path = _resolve_head_path(project_root)

        config_before = before.get("config")
        if isinstance(config_before, bytes):
            config_path.write_bytes(config_before)

        # D1: write HEAD_raw (the literal file bytes), not HEAD_resolved.
        # Preserves the `ref: refs/heads/<branch>\n` text so the worktree
        # stays attached.
        head_raw = before.get("HEAD_raw")
        if isinstance(head_raw, bytes):
            head_path.write_bytes(head_raw)

        refs_before = before.get("refs")
        packed_before_obj = before.get("packed_refs")
        packed_before: dict[str, str] = (
            packed_before_obj if isinstance(packed_before_obj, dict) else {}
        )
        if isinstance(refs_before, list):
            # Pass 1: write back every snapshot-before ref.
            ref_names_before: set[str] = set()
            for ref_name, ref_bytes in refs_before:
                if not isinstance(ref_name, str) or not isinstance(ref_bytes, bytes):
                    continue
                ref_names_before.add(ref_name)
                ref_path = common_dir / ref_name
                ref_path.parent.mkdir(parents=True, exist_ok=True)
                ref_path.write_bytes(ref_bytes)

            # Pass 2 (D2): delete refs that appeared during the test.
            # Walk current refs/heads and refs/tags; anything not in
            # ref_names_before is post-snapshot pollution and must go —
            # UNLESS its SHA was already in packed-refs at snapshot time
            # (Step 01-02: housekeeping promotion, not pollution).
            for category in ("heads", "tags"):
                refs_dir = common_dir / "refs" / category
                if not refs_dir.is_dir():
                    continue
                for ref_file in refs_dir.rglob("*"):
                    if not ref_file.is_file():
                        continue
                    ref_name = f"refs/{category}/" + str(
                        ref_file.relative_to(refs_dir)
                    ).replace(os.sep, "/")
                    if ref_name in ref_names_before:
                        continue
                    # Step 01-02: skip if this is a packed-to-loose
                    # promotion (SHA matches the packed-refs entry from
                    # the BEFORE snapshot). Don't destroy the legitimate
                    # ref the user owns.
                    current_sha = (
                        ref_file.read_bytes().decode("ascii", errors="replace").strip()
                    )
                    if packed_before.get(ref_name) == current_sha:
                        continue
                    ref_file.unlink(missing_ok=True)
    finally:
        _GUARD_RESTORE_IN_PROGRESS = False


@pytest.fixture(autouse=True)
def _git_pollution_guard():
    """Fail-fast if a test mutates host .git/{config,HEAD,refs/}.

    Snapshots before yield, snapshots after, computes the diff. On any
    non-empty diff: ATOMICALLY restore the snapshot (so the next test
    starts from a clean state) and THEN ``pytest.fail()`` naming the
    corruption type ("config", "HEAD", "refs"). Restore happens inside a
    try/finally so even if it raises, the test still fails with the
    original corruption message.

    Unlike ``guard_git_hooks`` which warns, this fixture uses
    ``pytest.fail()`` because config/HEAD/refs corruption — unlike hooks
    corruption — is immediately repo-breaking and must halt the suite.
    """
    if _GUARD_RESTORE_IN_PROGRESS:
        # Re-entry safety: never snapshot during a restore in flight.
        yield
        return

    before = _compute_git_state_snapshot(_PROJECT_ROOT)
    diff: list[str] = []
    try:
        yield
    finally:
        after = _compute_git_state_snapshot(_PROJECT_ROOT)
        diff = _diff_git_state(before, after)
        if diff:
            common_dir = _resolve_git_common_dir(_PROJECT_ROOT)
            if _common_git_dir_is_shared(common_dir):
                # Shared common .git: cannot attribute the diff to THIS test
                # vs a sibling worktree's legitimate change. Degrade to
                # WARN-ONLY — never restore (would clobber the sibling) and
                # never fail (the diff is most likely not ours).
                _warn_shared_common_dir_restore_skipped(
                    "config/HEAD/refs", diff, common_dir
                )
            else:
                try:
                    _atomic_restore_git_state(_PROJECT_ROOT, before)
                finally:
                    pytest.fail(
                        f"Test corrupted host git state: {diff}. "
                        "See docs/analysis/rca-test-git-pollution-2026-04-27.md "
                        "for the failure-mode lineage."
                    )


# ---------------------------------------------------------------------------
# 3a: HTML report branding (pytest-html hooks)
# ---------------------------------------------------------------------------


def pytest_html_report_title(report):
    """Set branded title for pytest-html report."""
    report.title = "nWave Test Report"


# ---------------------------------------------------------------------------
# pytest-bdd gherkin tag handling (root scope)
#
# pytest 9.1.0 (changelog #14442) re-enabled --strict-markers / --strict-config
# declared via addopts after they were silently ignored through 9.0.x. The suite
# carries pytest-bdd gherkin traceability tags (@US-3, @real-io,
# @contract-shape:bounded-change …) that are NOT registered markers. Without a
# pytest_bdd_apply_tag hook these surface as collection errors under the now-real
# strict-markers gate.
#
# This root hook applies a tag as a mark iff it is a registered marker, and
# otherwise consumes it (returns the function unchanged) so the gherkin metadata
# stays grep-able without generating strict-markers noise. Real
# @pytest.mark.<typo> mistakes remain rejected — only gherkin tags are consumed.
#
# The registered marker set is read live from the markers ini SSOT at hook-call
# time (no hard-coded duplicate list), so markers other conftests register
# dynamically via config.addinivalue_line are honoured too. Mirrors the per-track
# pattern in tests/installer/acceptance/installer_orphan_sweep/conftest.py.
#
# pytest_bdd_apply_tag is firstresult, and per-directory conftest hooks fire
# before the root conftest (pytest scope-precedence rule). The four existing
# per-track hooks always return non-None, so they win for their dirs via that
# ordering. This root hook only fires for tracks without a local hook.
# ---------------------------------------------------------------------------

_pytest_config = None


def pytest_configure(config):
    """Add project metadata to HTML report header; capture config for tag lookup."""
    global _pytest_config
    _pytest_config = config

    if hasattr(config, "_metadata"):
        config._metadata["Project"] = "nwave"
        config._metadata["Framework"] = "nWave"


def _registered_marker_names() -> set[str]:
    """Registered marker names from the markers ini (SSOT), read live.

    Resolved at hook-call time (during collection, after every conftest's
    pytest_configure has run) rather than snapshotted once — so markers
    registered dynamically via config.addinivalue_line in sub-conftests
    (e.g. the bug-track "failing" marker) are included. Snapshotting in
    pytest_configure raced that dynamic registration and could consume a
    marker another conftest depended on. Each entry is "name: description"
    → take the token before the first ":" or whitespace.
    """
    if _pytest_config is None:
        return set()
    return {
        entry.split(":", 1)[0].split()[0] for entry in _pytest_config.getini("markers")
    }


def pytest_bdd_apply_tag(tag, function):
    """Apply registered markers; consume gherkin metadata tags without marking."""
    if tag in _registered_marker_names():
        return getattr(pytest.mark, tag)(function)
    return function


def pytest_html_results_summary(prefix, summary, postfix):
    """Inject domain legend into HTML report summary."""
    prefix.extend(
        [
            "<h3>Test Domains</h3>",
            "<ul>",
            "<li><strong>DES</strong> — Developer Experience System</li>",
            "<li><strong>Installer</strong> — CLI installer and acceptance</li>",
            "<li><strong>Plugins</strong> — nWave plugins and install scripts</li>",
            "<li><strong>Acceptance</strong> — End-to-end acceptance tests</li>",
            "<li><strong>Bugs</strong> — Regression tests for tracked bugs</li>",
            "<li><strong>Release Train</strong> — Release pipeline script tests</li>",
            "</ul>",
        ]
    )


# ---------------------------------------------------------------------------
# 3b: Allure auto-labeling
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tier auto-marking: maps directory prefixes to pytest markers.
# Sorted by specificity at runtime (longest prefix wins).
# ---------------------------------------------------------------------------

TIER_MAP = {
    # DES tiers
    "tests/des/unit/": "unit",
    "tests/des/acceptance/": "acceptance",
    "tests/des/integration/": "integration",
    "tests/des/e2e/": "e2e",
    # Installer tiers
    "tests/installer/unit/": "unit",
    "tests/installer/acceptance/": "acceptance",
    "tests/installer/e2e/": "e2e",
    # Plugin tiers
    "tests/plugins/plugin-architecture/unit/": "unit",
    "tests/plugins/plugin-architecture/integration/": "integration",
    "tests/plugins/plugin-architecture/acceptance/": "acceptance",
    "tests/plugins/plugin-architecture/e2e/": "e2e",
    "tests/plugins/install/": "unit",
    "tests/plugins/": "unit",  # frontmatter tests default to unit
    # Build tiers
    "tests/build/acceptance/": "acceptance",
    "tests/build/unit/": "unit",
    "tests/build/": "unit",
    # Release train tests
    "tests/release/rc_smoke/acceptance/": "acceptance",
    "tests/release/": "unit",
    # Outcomes registry tiers
    "tests/outcomes/unit/": "unit",
    "tests/outcomes/acceptance/": "acceptance",
    # Bug regression tests
    "tests/bugs/": "acceptance",
    # Feature delta tiers
    "tests/feature_delta/unit/": "unit",
    "tests/feature_delta/acceptance/": "e2e",  # calls nwave-ai CLI; runs at e2e stage
    # Polyglot smoke tests (Kotlin/Rust/Go/Java/TS/C# builds) — not unit/acceptance
    "tests/polyglot-pilot/": "polyglot_smoke",
    # Root-level tests
    "tests/validation/": "unit",
    "tests/e2e/": "e2e",  # testcontainers-driven Docker tests (post Phase 5 retirement of Dockerfiles)
    "tests/": "unit",  # catch-all default
}

DOMAIN_MAP = {
    "tests/des/unit/": ("DES", "Unit Tests"),
    "tests/des/acceptance/": ("DES", "Acceptance Tests"),
    "tests/des/integration/": ("DES", "Integration Tests"),
    "tests/des/e2e/": ("DES", "E2E Tests"),
    "tests/des/": ("DES", "DES Tests"),
    "tests/installer/unit/git_workflow/": ("Installer", "Git Workflow"),
    "tests/installer/unit/": ("Installer", "Unit Tests"),
    "tests/installer/acceptance/installation/": (
        "Installer",
        "Installation Acceptance",
    ),
    "tests/installer/acceptance/installer/": ("Installer", "Installer Acceptance"),
    "tests/installer/acceptance/uninstaller/": ("Installer", "Uninstaller Acceptance"),
    "tests/installer/acceptance/": ("Installer", "Acceptance Tests"),
    "tests/installer/e2e/": ("Installer", "E2E Tests"),
    "tests/plugins/plugin-architecture/unit/": ("Plugins", "Unit Tests"),
    "tests/plugins/plugin-architecture/integration/": ("Plugins", "Integration Tests"),
    "tests/plugins/plugin-architecture/acceptance/": ("Plugins", "Acceptance Tests"),
    "tests/plugins/plugin-architecture/e2e/": ("Plugins", "E2E Tests"),
    "tests/plugins/install/": ("Plugins", "Install Scripts"),
    "tests/plugins/": ("Plugins", "nWave Plugins"),
    "tests/build/acceptance/": ("Build", "Plugin Acceptance"),
    "tests/build/unit/": ("Build", "Unit Tests"),
    "tests/build/": ("Build", "Build Tests"),
    "tests/bugs/": ("Bugs", "Regression"),
    "tests/release/rc_smoke/acceptance/": ("Release Train", "RC Smoke Acceptance"),
    "tests/release/": ("Release Train", "Unit Tests"),
}


# ---------------------------------------------------------------------------
# Top-level test-module guard (RCA Branch B structural defense).
#
# Tests must live under a tier subdirectory (tests/unit/, tests/installer/,
# tests/des/, etc.). Top-level ``tests/test_*.py`` modules historically
# drifted out of sync with their canonical siblings — the attribution
# worktree-isolation bug surfaced because the stale top-level duplicate
# carried tests that no longer matched the canonical version. Once the
# duplicate is gone, this guard prevents future regressions.
#
# Allowlist holds top-level modules that already exist on master and are
# scheduled for migration in a follow-up step. Adding a NEW top-level
# test module is the violation this guard catches.
# Structural rationale: top-level ``tests/test_*.py`` modules historically
# drifted out of sync with their canonical siblings (e.g. an attribution
# test had a stale top-level copy that lacked the isolation fixture used
# by the canonical version under ``tests/installer/unit/plugins/``). The
# 5-tier taxonomy (unit/integration/acceptance/e2e/...) is descriptive
# elsewhere; this guard makes it enforced.
# ---------------------------------------------------------------------------

_TOP_LEVEL_TEST_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Pre-existing top-level modules awaiting migration to a tier subdir.
        # Each of the following has a canonical sibling under tests/installer/
        # or tests/build/ — they are duplicates and will be deleted in a
        # follow-up step (out of scope for 02-01).
        "test_attribution_cli.py",
        "test_attribution_hook.py",
        "test_measure_adoption.py",
        "test_opencode_agents_skill_paths.py",
        "test_plugin_home_env_hardening.py",
        "test_python_path_resolution_in_skills.py",
        "test_reinforce_skill_loading.py",
        # No canonical sibling — keep at top level until migrated.
        "test_docgen.py",
        # Detective-guard self-validation harness (Step 01-01 of
        # fix-test-git-pollution). Lives at top level by design — it
        # validates the conftest-level autouse guard whose snapshot logic
        # is in this same file. Moving it to a subdir would obscure the
        # locality between guard implementation and its self-test.
        "test_guard_fixtures.py",
    }
)


def _is_offending_top_level_test(rel_path: str) -> bool:
    """True iff ``rel_path`` is a top-level ``test_*.py`` and not allowlisted.

    Pure function. ``rel_path`` is normalized with forward slashes,
    relative to the tests root.
    """
    parts = rel_path.split("/")
    if len(parts) != 1:
        return False
    name = parts[0]
    if not (name.startswith("test_") and name.endswith(".py")):
        return False
    return name not in _TOP_LEVEL_TEST_ALLOWLIST


# ---------------------------------------------------------------------------
# Shared-state serialization guard: pin every test that drives a subprocess
# with cwd=<real repo> onto one xdist worker group (2026-06-21).
#
# Symptom: under the pre-push leg
#   pytest -m "unit or integration or acceptance" -n 2 --dist=loadgroup
# tests pass in isolation but fail ORDER-DEPENDENTLY in-suite (e.g.
# slice-04 carpaccio, feature_delta slice-02/03 cascade).
#
# Root cause: ~40+ test suites spawn `des`/CLI subprocesses with
# ``cwd=_REPO_ROOT`` (the real repo). Those subprocesses read/write the
# repo's SHARED .nwave state — ``.nwave/wave-active/active.json`` (the wave
# floor read by pre_tool_use_handler via Path.cwd()) and the
# ``.nwave/telemetry/...`` event logs. Two such tests landing on the SAME
# worker collide on that shared on-disk state.
#
# Fix (test-infra only, no production change): detect cwd=real-repo
# dependence by scanning the item's own test module AND its sibling
# ``*composition*.py`` / ``*steps*/`` modules for a ``cwd=<real repo>``
# subprocess call (most suites keep the call in a composition / step module
# the test imports, not in the test file itself), then pin the item to the
# ``real_repo_scan`` xdist group. Under ``--dist=loadgroup`` every member of
# that group runs on one worker — serialized, never concurrent. This mirrors
# the manual pin already present in four suite-local conftests (e.g.
# tests/des/acceptance/atdd_pure_common_audit_log_ssot/conftest.py),
# generalised so new suites are covered automatically without a hardcoded
# path list.
# ---------------------------------------------------------------------------

# A subprocess ``cwd=`` argument that resolves to the REAL repo checkout is
# the load-bearing signal — NOT the anchor variable's name (suites spell it
# ``_REPO_ROOT``, ``REPO_ROOT``, ``PROJECT_ROOT``, ``_repo_root()``,
# ``Path.cwd()`` interchangeably). We match the ``cwd=`` keyword immediately
# followed by such an anchor. ``cwd=tmp_path`` / ``cwd=sandbox`` /
# ``cwd=tmp_repo`` etc. deliberately do NOT match: those subprocesses run in
# an isolated tmp dir and never touch the shared .nwave state.
_REAL_REPO_CWD_RE = re.compile(
    r"""\b cwd \s* = \s*             # the cwd keyword argument (word-boundary:
                                      # excludes prev_cwd=/original_cwd=/etc.)
        (?: str \s* \( \s* )?        # optional str( wrapper
        (?:
            _? REPO_ROOT             # _REPO_ROOT / REPO_ROOT
          | _? PROJECT_ROOT          # _PROJECT_ROOT / PROJECT_ROOT
          | _repo_root \s* \(        # _repo_root()
          | Path \s* \. \s* cwd \s* \(  # Path.cwd()
        )
    """,
    re.VERBOSE,
)

# Per-FILE cache: a single source file -> does it drive a cwd=<real repo>
# subprocess? Per-file (not per-directory) granularity matters: a directory
# may hold one cwd=repo test next to dozens of pure unit tests; pinning the
# whole directory would over-serialize the innocent ones onto the single
# worker and inflate the suite wall-time. We scan the item's OWN test module
# plus the directory's ``*composition*.py`` and ``*steps*/`` modules (which
# BDD suites import), but NOT sibling ``test_*.py`` modules (tests do not
# import one another).
_real_repo_file_cache: dict[Path, bool] = {}


def _file_drives_real_repo_cwd(path: Path) -> bool:
    """True iff ``path``'s source contains a ``cwd=<real repo>`` subprocess call.

    Cached per file. Read errors are treated as "no" (worst case is a missed
    pin, never a false abort).
    """
    cached = _real_repo_file_cache.get(path)
    if cached is not None:
        return cached
    try:
        found = bool(_REAL_REPO_CWD_RE.search(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError):
        found = False
    _real_repo_file_cache[path] = found
    return found


# Placed HERE rather than at module top so it introduces no line shift above
# line ~354 (see the note in `_local_imports`: a test pins subprocess.run
# timeout sites in this file by absolute line number).
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import ast


def _resolve_import_targets(source_file: Path, node: ast.AST) -> list[Path]:
    """Resolve one import statement to the local .py file(s) it can name.

    Handles BOTH import forms and BOTH addressing modes:

    * ``from . import x`` / ``from .steps.composition import y`` — RELATIVE:
      resolved against the importing file's package directory, walking up
      ``level - 1`` parents.
    * ``import tests.des.acceptance.x.steps.y`` / ``from tests.... import z`` —
      ABSOLUTE: resolved from the repo root (the ``tests`` package is
      importable from there).

    For a dotted tail ``a.b.c`` both ``a/b/c.py`` and ``a/b/c/__init__.py`` are
    candidates, and so is ``a/b.py`` (the ``from a.b import c`` case where
    ``c`` is a NAME inside module ``b``, not a submodule). Returning a
    superset is the safe direction: an unresolvable or over-resolved import
    can only ever ADD a pin, never drop one.
    """
    import ast  # function-local: see the note in `_local_imports`

    repo_root = Path(__file__).resolve().parent.parent
    bases: list[Path] = []
    parts: list[str] = []

    if isinstance(node, ast.ImportFrom):
        if node.level:
            base = source_file.parent
            for _ in range(node.level - 1):
                base = base.parent
            bases = [base]
        else:
            bases = [repo_root]
        parts = (node.module or "").split(".") if node.module else []
        # `from a.b import c` — `c` may itself be a submodule.
        tails = [[*parts, alias.name.split(".")[0]] for alias in node.names]
        tails.append(parts)
    elif isinstance(node, ast.Import):
        bases = [repo_root]
        tails = [alias.name.split(".") for alias in node.names]
    else:
        return []

    resolved: list[Path] = []
    for base in bases:
        for tail in tails:
            tail = [p for p in tail if p]
            if not tail:
                continue
            joined = base.joinpath(*tail)
            resolved.append(joined.with_suffix(".py"))
            resolved.append(joined / "__init__.py")
            if len(tail) > 1:
                resolved.append(base.joinpath(*tail[:-1]).with_suffix(".py"))
    return resolved


# Per-FILE cache of a module's resolved local imports (the AST parse + path
# resolution is the expensive part and is a pure function of the file).
_module_imports_cache: dict[Path, tuple[Path, ...]] = {}


def _local_imports(path: Path) -> tuple[Path, ...]:
    """Return the existing, in-repo .py files ``path`` imports.

    Parse errors / unreadable files yield ``()`` — worst case a missed pin,
    never a false abort (same failure posture as ``_file_drives_real_repo_cwd``).
    """
    # Imported function-locally, NOT at module scope, on purpose: a new
    # top-level import here shifts every line below it by one, and
    # `tests/bugs/installer/acceptance/steps/test_subprocess_timeout_calibration.py`
    # pins subprocess.run timeout sites in this file by absolute LINE NUMBER.
    # A module-level import would break that table (56 -> 57) for a pure
    # bookkeeping reason. Keeping it local costs nothing (the cache below means
    # this runs once per file) and leaves the line coordinates untouched.
    import ast

    cached = _module_imports_cache.get(path)
    if cached is not None:
        return cached
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        _module_imports_cache[path] = ()
        return ()
    # Confine the closure to the TEST tree. The detector's signal is a TEST
    # pointing a subprocess at the real repo checkout -- production modules
    # under `src/` legitimately spawn subprocesses with `cwd=Path.cwd()` as
    # their normal behaviour, and following imports into them matches that
    # production pattern instead, pinning nearly the whole suite (measured:
    # 1221 of 1220 test files vs 254 under the old glob). The superseded glob
    # likewise only ever scanned test-side siblings; this preserves that
    # boundary while making reachability precise inside it.
    tests_root = Path(__file__).resolve().parent
    found: list[Path] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for candidate in _resolve_import_targets(path, node):
                if not candidate.is_file():
                    continue
                resolved = candidate.resolve()
                if tests_root in resolved.parents:
                    found.append(resolved)
    result = tuple(dict.fromkeys(found))
    _module_imports_cache[path] = result
    return result


def _conftest_chain(test_file: Path) -> list[Path]:
    """Every ``conftest.py`` pytest applies to ``test_file``, nearest-first.

    A pytest-bdd suite frequently registers its step definitions by importing
    the step package from the SUITE conftest rather than from the test module
    (``scenarios()`` binds them by side effect). Those conftests are therefore
    genuine roots of the import closure — omitting them would under-pin a test
    that really does drive a ``cwd=<real repo>`` subprocess.

    SUITE-LOCAL conftests only: this ROOT ``tests/conftest.py`` is deliberately
    excluded. It applies to EVERY test, so including it carries zero
    discriminating information -- and it does contain one real
    ``cwd=str(_PROJECT_ROOT)`` call (the ``shared_wheel`` fixture), which would
    therefore pin 100% of the suite into the serialized group, i.e. no
    parallelism at all. That call is not the defect class this pin guards:
    it is session-scoped, ``FileLock``-guarded, runs ``python -m build
    --wheel`` and writes only to a shared tmp wheel dir -- it never touches
    the per-test ``.nwave`` state the group exists to protect.
    """
    tests_root = Path(__file__).resolve().parent
    chain: list[Path] = []
    current = test_file.resolve().parent
    while True:
        candidate = current / "conftest.py"
        if candidate.is_file() and candidate.parent != tests_root:
            chain.append(candidate)
        if current == tests_root or tests_root not in current.parents:
            break
        current = current.parent
    return chain


# Per-FILE cache for the item-level scan. `pytest_collection_modifyitems` calls
# this once PER ITEM (thousands of times), but the result depends only on
# ``test_file`` -- and the body globs the test dir (composition*.py + steps/**)
# on every call. Without memoization those directory globs run once per item
# (O(items x globs)); a same-file test module with 40 test functions re-globs
# its dir 40 times. Memoizing by ``test_file`` collapses the thousands of calls
# to one-per-unique-file, which is the dominant cost of whole-tree collection
# (the `des run-contract-gate --collect-only` subprocess the acceptance poles
# spawn). Pure function of the filesystem, stable within a run.
_real_repo_item_cache: dict[Path, bool] = {}


def _item_depends_on_real_repo(test_file: Path) -> bool:
    """True iff this test item drives a cwd=<real repo> subprocess.

    Scans, at per-file granularity:

    1. The item's OWN test module — direct ``cwd=<real repo>`` usage.
    2. The directory's ``*composition*.py`` modules — BDD suites keep the
       subprocess-spawning steps in a composition module the test imports.
    3. Modules under any ``*steps*`` subdirectory — pytest-bdd step
       definitions (named ``steps/``, ``<feature>_steps/``, ``gate_steps/``,
       or ``acceptance/steps/``).

    Sibling ``test_*.py`` modules are deliberately NOT scanned: pytest test
    modules do not import one another, so a cwd=repo test does not implicate
    its innocent unit-test neighbours. This keeps the ``real_repo_scan``
    worker group tight and the suite parallel where it safely can be.

    Memoized by ``test_file`` (see ``_real_repo_item_cache``): the directory
    globs below must not re-run once per item in a same-file module.
    """
    cached = _real_repo_item_cache.get(test_file)
    if cached is not None:
        return cached
    result = _compute_item_depends_on_real_repo(test_file)
    _real_repo_item_cache[test_file] = result
    return result


def _compute_item_depends_on_real_repo(test_file: Path) -> bool:
    """Uncached body of :func:`_item_depends_on_real_repo` (memoized wrapper).

    Walks the test's REAL import closure — the test module itself, the
    ``conftest.py`` chain pytest applies to it, and every in-repo module those
    transitively import — and pins iff some module in that closure drives a
    ``cwd=<real repo>`` subprocess.

    This replaces the previous DIRECTORY-GLOB expansion (every
    ``*composition*.py`` and ``steps/**`` sibling of the test's directory,
    imported or not). That glob was an ~8x over-approximation: one matching
    module pinned its entire directory, so 32 directly-matching files became
    254 pinned files, and the serialized ``real_repo_scan`` group swallowed
    17.2% of collected items (~84.7% of suite wall time — the group is ~27x
    more expensive per item). Import-reachability is the load-bearing
    property the glob was approximating: a test can only touch the shared
    ``.nwave`` state through code it actually imports.

    Safety posture is unchanged-or-tighter in the pin direction: unresolvable
    imports, parse errors and dotted-tail ambiguity all resolve to a SUPERSET
    of candidates (see ``_resolve_import_targets``), so the closure can
    over-pin but never silently under-pin a genuine cwd=repo driver.
    """
    roots = [test_file.resolve(), *_conftest_chain(test_file)]
    seen: set[Path] = set()
    queue = list(roots)
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        if _file_drives_real_repo_cwd(current):
            return True
        queue.extend(dep for dep in _local_imports(current) if dep not in seen)
    return False


def pytest_collection_modifyitems(config, items):
    """Auto-label tests with Allure labels and tier markers from file paths.

    Also enforces the top-level test-module guard (RCA Branch B): any
    ``tests/test_*.py`` not on the allowlist aborts collection with a
    descriptive error.

    Finally pins every test whose suite drives a cwd=<real repo> subprocess
    onto the ``real_repo_scan`` xdist group so they serialize on one worker
    (shared .nwave state isolation — see the block above).
    """
    # --- Top-level module guard (fail-fast before any other work) ---
    tests_root = Path(__file__).parent
    offenders: list[str] = []
    for item in items:
        try:
            rel = Path(item.fspath).resolve().relative_to(tests_root.resolve())
        except ValueError:
            # Item lives outside the tests root (e.g. doctest in src/).
            continue
        rel_str = str(rel).replace(os.sep, "/")
        if _is_offending_top_level_test(rel_str):
            offenders.append(rel_str)

    if offenders:
        raise pytest.UsageError(
            "Stale top-level test module(s) detected: "
            + ", ".join(sorted(set(offenders)))
            + ". Tests must live under a tier subdirectory "
            + "(tests/unit/, tests/installer/, tests/des/, tests/build/, etc.). "
            + "Top-level modules historically drifted out of sync with their "
            + "canonical tier siblings; this guard enforces the 5-tier taxonomy."
        )

    try:
        import allure

        # Importability is NOT enough: a run that disables the plugin with
        # `-p no:allure_pytest` (the contract-gate collection does this for speed)
        # leaves `allure` importable but its plugin unregistered, so `allure.epic()`
        # returns a non-marker and `add_marker` raises. Gate the labeling on the
        # plugin actually being ACTIVE, not merely installed.
        has_allure = config.pluginmanager.hasplugin("allure_pytest")
    except ImportError:
        has_allure = False

    # Pre-sort TIER_MAP prefixes by length descending (longest/most-specific first)
    sorted_tier_prefixes = sorted(TIER_MAP.keys(), key=len, reverse=True)

    for item in items:
        rel_path = os.path.relpath(item.fspath, config.rootdir)
        rel_path = rel_path.replace(os.sep, "/")

        # --- Allure labeling (unchanged, conditional on allure) ---
        if has_allure:
            matched_epic = None
            matched_feature = None
            matched_len = 0
            for prefix, (epic, feature) in DOMAIN_MAP.items():
                if rel_path.startswith(prefix) and len(prefix) > matched_len:
                    matched_epic = epic
                    matched_feature = feature
                    matched_len = len(prefix)

            if matched_epic:
                item.add_marker(allure.epic(matched_epic))
                item.add_marker(allure.feature(matched_feature))

            if item.cls:
                item.add_marker(allure.story(item.cls.__name__))

        # --- Tier auto-marking (always runs) ---
        for prefix in sorted_tier_prefixes:
            if rel_path.startswith(prefix):
                tier = TIER_MAP[prefix]
                item.add_marker(getattr(pytest.mark, tier))
                break

        # --- Shared-state serialization pin (always runs) ---
        # If this item's suite drives a cwd=<real repo> subprocess (touching
        # the shared .nwave state), pin it to one xdist worker group so the
        # loadgroup scheduler never races two such tests across workers.
        item_path = getattr(item, "path", None)
        if item_path is not None and _item_depends_on_real_repo(Path(item_path)):
            item.add_marker(pytest.mark.xdist_group("real_repo_scan"))

        # --- Docker-heavy e2e: run ONLY in CI, never locally (Ale 2026-07-06) ---
        # tests/e2e/ install tests spin up testcontainers/Docker. Locally they
        # contend for the Docker daemon + memory under `-n auto`, flake, and are
        # slow -- and they reddened the DES feature-end full-suite leg twice,
        # refusing the wire-p0-gates seal (F-E2E-INSTALL-FLAKY). Decision: run them
        # ONLY in CI (fresh runners, no contention; ADR-PLAT-010). Locally they are
        # SKIPPED unless NWAVE_RUN_DOCKER_E2E=1 forces them. When they DO run (CI),
        # pin them to one xdist_group so they serialize among themselves.
        if rel_path.startswith("tests/e2e/"):
            item.add_marker(pytest.mark.xdist_group("e2e_docker_install"))
            if not (os.environ.get("CI") or os.environ.get("NWAVE_RUN_DOCKER_E2E")):
                item.add_marker(
                    pytest.mark.skip(
                        reason="Docker e2e runs only in CI (F-E2E-INSTALL-FLAKY / "
                        "ADR-PLAT-010); set NWAVE_RUN_DOCKER_E2E=1 to run locally"
                    )
                )


# ---------------------------------------------------------------------------
# 3c: Rich terminal summary table
# ---------------------------------------------------------------------------


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Render a Rich table with pass/fail/skip/xfail counts per domain."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        return

    domain_labels = {
        "tests/des/unit/": "DES (unit)",
        "tests/des/acceptance/": "DES (acceptance)",
        "tests/des/integration/": "DES (integration)",
        "tests/des/e2e/": "DES (e2e)",
        "tests/des/": "DES",
        "tests/installer/unit/git_workflow/": "Installer (git)",
        "tests/installer/unit/": "Installer (unit)",
        "tests/installer/acceptance/installation/": "Installer (installation)",
        "tests/installer/acceptance/installer/": "Installer (walking skeleton)",
        "tests/installer/acceptance/uninstaller/": "Installer (uninstaller)",
        "tests/installer/acceptance/": "Installer (acceptance)",
        "tests/installer/e2e/": "Installer (e2e)",
        "tests/plugins/plugin-architecture/unit/": "Plugins (unit)",
        "tests/plugins/plugin-architecture/integration/": "Plugins (integration)",
        "tests/plugins/plugin-architecture/acceptance/": "Plugins (acceptance)",
        "tests/plugins/plugin-architecture/e2e/": "Plugins (e2e)",
        "tests/plugins/install/": "Plugins (install)",
        "tests/plugins/": "Plugins",
        "tests/bugs/": "Bugs",
        "tests/release/": "Release Train",
    }

    # Sorted by specificity (longest prefix first)
    sorted_prefixes = sorted(domain_labels.keys(), key=len, reverse=True)

    stats = {}
    for label in domain_labels.values():
        stats[label] = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0}

    category_keys = {
        "passed": "passed",
        "failed": "failed",
        "error": "failed",
        "skipped": "skipped",
        "xfailed": "xfailed",
        "xpassed": "passed",
    }

    for cat, outcome_key in category_keys.items():
        for report in terminalreporter.getreports(cat):
            if not hasattr(report, "fspath") or report.fspath is None:
                continue
            rel = os.path.relpath(str(report.fspath), str(config.rootdir))
            rel = rel.replace(os.sep, "/")

            matched_label = "Other"
            for prefix in sorted_prefixes:
                if rel.startswith(prefix):
                    matched_label = domain_labels[prefix]
                    break

            if matched_label not in stats:
                stats[matched_label] = {
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "xfailed": 0,
                }
            stats[matched_label][outcome_key] += 1

    # Remove domains with zero tests
    stats = {k: v for k, v in stats.items() if sum(v.values()) > 0}
    if not stats:
        return

    table = Table(title="Test Results by Domain", show_lines=True)
    table.add_column("Domain", style="bold")
    table.add_column("Passed", style="green", justify="right")
    table.add_column("Failed", style="red", justify="right")
    table.add_column("Skipped", style="yellow", justify="right")
    table.add_column("XFailed", style="cyan", justify="right")
    table.add_column("Total", style="bold", justify="right")

    totals = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0}
    for domain in sorted(stats.keys()):
        counts = stats[domain]
        total = sum(counts.values())
        table.add_row(
            domain,
            str(counts["passed"]),
            str(counts["failed"]),
            str(counts["skipped"]),
            str(counts["xfailed"]),
            str(total),
        )
        for k in totals:
            totals[k] += counts[k]

    grand_total = sum(totals.values())
    table.add_row(
        "TOTAL",
        str(totals["passed"]),
        str(totals["failed"]),
        str(totals["skipped"]),
        str(totals["xfailed"]),
        str(grand_total),
        style="bold",
    )

    console = Console()
    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# 3d: Machine-readable test result (SF sister Q-41 — cross-repo convention)
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session, exitstatus):
    """Emit a machine-readable test result: a tagged stdout line + sidecar.

    SEPARATE hook from ``pytest_terminal_summary`` (the Rich table) on
    purpose — Python keeps only the last binding of a given hook name, so a
    second ``pytest_terminal_summary`` would shadow the table. ``pytest_
    sessionfinish`` coexists. Lets tooling read pass/fail counts without
    parsing the Rich table. Zero new dependencies.

    Line format: ``NWAVE_TEST_RESULT:{json}``. Sidecar file path (optional)
    via the ``NWAVE_TEST_RESULT_FILE`` env var.
    """
    import json

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    stats = reporter.stats

    def _n(key: str) -> int:
        return len(stats.get(key, []))

    result = {
        "passed": _n("passed") + _n("xpassed"),
        "failed": _n("failed") + _n("error"),
        "skipped": _n("skipped"),
        "xfailed": _n("xfailed"),
        "exit_status": int(exitstatus),
    }
    line = "NWAVE_TEST_RESULT:" + json.dumps(result, separators=(",", ":"))
    print(line)

    sidecar = os.environ.get("NWAVE_TEST_RESULT_FILE")
    if sidecar:
        try:
            Path(sidecar).write_text(line + "\n", encoding="utf-8")
        except OSError:
            pass

    _flush_test_durations(session.config)


# ---------------------------------------------------------------------------
# 3e: Always-on per-test duration capture.
#
# EVERY run records the wall-clock of EVERY phase of EVERY test, so "which
# tests are slow?" is answerable from ANY run -- never a re-run with
# `--durations`, never a top-N window that hides the long tail (200 tests at 3s
# outweigh the slowest 15 and no `--durations=15` ever shows them).
#
# Written to a FILE, never stdout, on purpose: `--durations=0` in `addopts`
# would dump one line per phase (~20k on this tree) into EVERY run's output --
# including the `des` gates that PARSE that output (commit-slice,
# run-contract-gate) and every targeted crafter run. The file costs nothing to
# ignore and everything to have.
#
# xdist-safe: the CONTROLLER truncates once at session start; each worker
# appends its own batch at session finish, so the file holds exactly one run.
# Analyse with `uv run poe test-durations` (aggregates by test/file/dir).
# ---------------------------------------------------------------------------

_TEST_DURATIONS: list[dict[str, object]] = []


def _durations_path() -> Path:
    """The always-on per-test duration log (gitignored; env-overridable)."""
    override = os.environ.get("NWAVE_TEST_DURATIONS_FILE")
    return (
        Path(override)
        if override
        else _PROJECT_ROOT / ".nwave" / "test-durations.jsonl"
    )


def pytest_sessionstart(session):
    """Truncate the duration log once per run (controller only, never workers)."""
    if hasattr(session.config, "workerinput"):
        return  # an xdist worker — the controller already truncated
    try:
        path = _durations_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except OSError:
        pass  # profiling must never fail a run


def pytest_runtest_logreport(report):
    """Record every phase's wall-clock (setup + call + teardown, per test)."""
    _TEST_DURATIONS.append(
        {
            "nodeid": report.nodeid,
            "when": report.when,
            "duration": round(report.duration, 4),
            "outcome": report.outcome,
        }
    )


def _flush_test_durations(config) -> None:
    """Append this session's (or this xdist worker's) duration batch."""
    if not _TEST_DURATIONS:
        return
    import json

    try:
        path = _durations_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for record in _TEST_DURATIONS:
                fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        pass  # profiling must never fail a run
