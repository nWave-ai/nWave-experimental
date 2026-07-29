"""Regression: the cargo committed-scope digest must reuse the caller's warm
``target/`` build-cache when the target root is a LINKED git worktree, never
cold-compile from scratch.

RCA: ``src/des/adapters/driven/runner/cargo_runner.py`` ``_env_with_cargo_dir``
(~258-268) copies ``os.environ`` and prepends the resolved cargo's dir to
``PATH`` but NEVER sets ``CARGO_TARGET_DIR``. Both ``run_cargo_scope`` and
``list_cargo_scope`` (the run + enumerate facets ``des commit-slice`` shells
for the committed-scope digest) route through this ONE seam. When the
``--repo`` handed to the digest is a fresh/linked worktree with no warm
``target/`` of its own, ``cargo nextest list`` cold-compiles the whole crate --
on a big crate this OOMs or returns 0 identities, which ``list_cargo_scope``
maps to ``RunnerAdapterUnavailable`` -> ``SliceCommitIndeterminate``, blocking
the slice.

Fixed behaviour pinned here (env-injection level, NO real cargo build):

1. ``CARGO_TARGET_DIR`` already present in the inherited env (operator/CI set
   it) -> left UNTOUCHED (never override an explicit operator choice).
2. Target root is a LINKED git worktree (resolvable via
   ``git rev-parse --git-common-dir`` pointing at a different, main checkout)
   -> ``CARGO_TARGET_DIR`` is set to ``<main-checkout>/target``.
3. Anything else -- a plain (non-worktree) repo, ``git`` absent, or any
   resolution failure -- env is left UNTOUCHED (today's behavior),
   degrade-LOUD, never a crash and never a guessed dir.

CI-SAFE / no real cargo build: cargo resolution is stubbed
(``cargo_runner.resolve_tool``) and the shelled CARGO subprocess call is
captured rather than executed. The ``git`` subprocess calls the (future) fix
issues to probe the worktree ARE real (routed to the genuine
``subprocess.run``) against REAL git fixture repos built with
``git init`` / ``git worktree add`` -- fast, no compilation, no cargo/nextest
ever invoked. Distinguished from the stubbed cargo call by
``Path(argv[0]).name`` (works whether the fix hardcodes ``"git"`` or resolves
an absolute git path).

Driving surface (Mandate-13 driving-port-only): ``run_cargo_scope`` /
``list_cargo_scope`` ARE the driven-runner adapter's own production entry
points (the objects under regression), mirroring the established
``tests/bugs/des/test_cargo_scope_nomatch_is_indeterminate.py`` adapter-direct
precedent -- the seam under test (``_env_with_cargo_dir``) is private and
carries no target_root parameter today, so the AT drives it through its two
real callers rather than coupling to a signature the fix has not chosen yet.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.runner import cargo_runner
from des.adapters.driven.runner.tool_discovery import ToolResolution
from des.ports.test_runner_port import (
    ListScope,
    RunnerAdapter,
    RunVerdict,
)


_ADAPTER = RunnerAdapter(name="cargo-test")
_SCOPED_COMMAND = ("cargo", "nextest", "run", "--test", "ws_driver")
# Non-empty nextest-list-shaped stdout so the list facet does not itself raise
# an (unrelated) empty-scope INDETERMINATE -- see `_parse_nextest_list`.
_LIST_STDOUT = "ws_driver it_works\n"


# --- fixture builders: REAL git, zero cargo/compilation ---------------------


def _run_git(cwd: Path, *args: str) -> None:
    """A REAL, unstubbed git subprocess -- used only during fixture setup,
    BEFORE any test body applies its ``subprocess.run`` monkeypatch."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _seed_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", "seed")


def _main_checkout_with_linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A REAL main checkout + a REAL linked ``git worktree`` (no cargo/build).

    Mirrors the exact shape ``des commit-slice`` hands the digest per the RCA:
    a fresh/linked worktree with no warm ``target/`` of its own, while the
    MAIN checkout carries one.
    """
    main = tmp_path / "main-checkout"
    _seed_repo(main)
    (main / "target").mkdir()  # the warm build-cache the fix must point back to
    worktree = tmp_path / "linked-worktree"
    _run_git(main, "worktree", "add", "-q", "-b", "wt-branch", str(worktree), "HEAD")
    return main, worktree


def _plain_repo(tmp_path: Path) -> Path:
    """A REAL plain (non-worktree) git repo -- the negative-guard target."""
    repo = tmp_path / "plain-repo"
    _seed_repo(repo)
    return repo


# --- stubs: cargo resolution + captured cargo subprocess ---------------------


def _stub_cargo_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """cargo "resolves" to a fake path -- no real cargo binary is touched."""
    monkeypatch.setattr(
        cargo_runner,
        "resolve_tool",
        lambda name, known_locations, **_kwargs: ToolResolution(
            rung="on-path", path="/fake/cargo"
        ),
    )


def _stub_cargo_call(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, Any],
    *,
    cargo_returncode: int = 0,
    cargo_stdout: str = "",
    git_raises: bool = False,
) -> None:
    """Route ``git`` argv through the REAL ``subprocess.run`` (so the fix's
    worktree-resolution probe exercises the genuine fixture repos); route the
    CARGO argv through a capturing fake (no real cargo/nextest is ever
    spawned). Distinguished by ``Path(argv[0]).name`` -- robust whether the
    fix hardcodes the literal ``"git"`` or resolves an absolute git path.
    """
    real_run = subprocess.run

    def _fake(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv and Path(argv[0]).name == "git":
            if git_raises:
                raise FileNotFoundError("git executable not found (simulated)")
            return real_run(argv, **kwargs)
        captured["env"] = kwargs.get("env")
        captured["cwd"] = kwargs.get("cwd")
        captured["argv"] = argv
        return subprocess.CompletedProcess(
            args=argv, returncode=cargo_returncode, stdout=cargo_stdout, stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake)


def _invoke_facet(facet: str, target_root: Path) -> RunVerdict | ListScope:
    if facet == "run":
        return cargo_runner.run_cargo_scope(_ADAPTER, target_root, _SCOPED_COMMAND)
    return cargo_runner.list_cargo_scope(_ADAPTER, target_root)


_FACETS = ["run", "list"]


# --- POSITIVE (active-RED today) --------------------------------------------


@pytest.mark.parametrize("facet", _FACETS)
def test_cargo_digest_env_reuses_main_checkout_target_dir_for_linked_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, facet: str
) -> None:
    """A fresh/linked worktree handed to the digest must resolve
    ``CARGO_TARGET_DIR`` to the MAIN checkout's warm ``target/`` -- both the
    run facet (``run_cargo_scope``) and the enumerate facet
    (``list_cargo_scope``) route through the SAME ``_env_with_cargo_dir``
    seam (the RCA), so both must reuse the cache.

    Active-RED at HEAD: ``_env_with_cargo_dir`` never sets
    ``CARGO_TARGET_DIR`` at all -- the shelled cargo subprocess inherits the
    caller's (copied) env unchanged, so ``env.get("CARGO_TARGET_DIR")`` is
    ``None`` and this assertion fails for the right (business) reason, never
    an import/collection error.
    """
    monkeypatch.delenv("CARGO_TARGET_DIR", raising=False)
    main, worktree = _main_checkout_with_linked_worktree(tmp_path)
    captured: dict[str, Any] = {}
    _stub_cargo_resolved(monkeypatch)
    _stub_cargo_call(monkeypatch, captured, cargo_stdout=_LIST_STDOUT)

    _invoke_facet(facet, worktree)

    env = captured.get("env")
    assert env is not None, "the cargo subprocess must be shelled with an explicit env"
    assert env.get("CARGO_TARGET_DIR") == str(main / "target"), (
        "CARGO_TARGET_DIR must resolve to the MAIN checkout's target/ dir for "
        f"a linked worktree; got {env.get('CARGO_TARGET_DIR')!r}"
    )


# --- NEGATIVE (green now AND after -- the guard paths must NOT regress) ----


@pytest.mark.negative_at
@pytest.mark.parametrize("facet", _FACETS)
def test_cargo_digest_env_preserves_operator_set_cargo_target_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, facet: str
) -> None:
    """An operator/CI-set ``CARGO_TARGET_DIR`` must NEVER be overridden, even
    when the target IS a linked worktree that would otherwise trigger the
    reuse-injection (negative-guard: an explicit operator choice always wins).

    Passes TODAY (the function touches nothing) -- must keep passing after
    the fix.
    """
    explicit = str(tmp_path / "explicit-operator-target")
    monkeypatch.setenv("CARGO_TARGET_DIR", explicit)
    _main, worktree = _main_checkout_with_linked_worktree(tmp_path)
    captured: dict[str, Any] = {}
    _stub_cargo_resolved(monkeypatch)
    _stub_cargo_call(monkeypatch, captured, cargo_stdout=_LIST_STDOUT)

    _invoke_facet(facet, worktree)

    assert captured["env"].get("CARGO_TARGET_DIR") == explicit, (
        "an already-set CARGO_TARGET_DIR must be left untouched (operator "
        "choice wins), never overridden by the worktree-reuse injection"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("facet", _FACETS)
def test_cargo_digest_env_leaves_plain_non_worktree_repo_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, facet: str
) -> None:
    """A plain (non-worktree) repo must NOT get a fabricated
    ``CARGO_TARGET_DIR`` -- injecting one for a repo that already owns its own
    ``target/`` would be WRONG, not merely unnecessary.

    Passes TODAY -- must keep passing after the fix.
    """
    monkeypatch.delenv("CARGO_TARGET_DIR", raising=False)
    repo = _plain_repo(tmp_path)
    captured: dict[str, Any] = {}
    _stub_cargo_resolved(monkeypatch)
    _stub_cargo_call(monkeypatch, captured, cargo_stdout=_LIST_STDOUT)

    _invoke_facet(facet, repo)

    assert "CARGO_TARGET_DIR" not in captured["env"], (
        "a plain non-worktree repo must not have CARGO_TARGET_DIR injected; "
        f"got {captured['env'].get('CARGO_TARGET_DIR')!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("facet", _FACETS)
def test_cargo_digest_env_degrades_loud_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, facet: str
) -> None:
    """``git`` absent (or the worktree-resolution probe erroring) must NEVER
    crash the digest and must NEVER guess a wrong target dir -- degrade-LOUD
    to today's untouched-env behavior, the digest still completes.

    Passes TODAY -- must keep passing after the fix.
    """
    monkeypatch.delenv("CARGO_TARGET_DIR", raising=False)
    _main, worktree = _main_checkout_with_linked_worktree(tmp_path)
    captured: dict[str, Any] = {}
    _stub_cargo_resolved(monkeypatch)
    _stub_cargo_call(monkeypatch, captured, cargo_stdout=_LIST_STDOUT, git_raises=True)

    result = _invoke_facet(facet, worktree)

    assert "CARGO_TARGET_DIR" not in captured["env"], (
        "git-unavailable must degrade to an untouched env, never guess a dir"
    )
    if facet == "run":
        assert isinstance(result, RunVerdict) and result.passed is True
    else:
        assert isinstance(result, ListScope) and result.node_ids
    # no crash propagated past `_env_with_cargo_dir` -- the digest completed.


@pytest.mark.negative_at
def test_verify_fresh_clone_gate_does_not_import_cargo_runner() -> None:
    """``verify_fresh_clone.py`` is a structurally SEPARATE true-scratch gate
    (never routes through the committed-scope digest) -- the worktree-reuse
    fix here must not weaken it. Guard: it carries no import of
    ``cargo_runner`` today AND must not gain one.
    """
    import des.cli.verify_fresh_clone as verify_fresh_clone_module

    source = Path(verify_fresh_clone_module.__file__).read_text(encoding="utf-8")

    assert "cargo_runner" not in source, (
        "verify_fresh_clone.py must stay structurally independent of "
        "cargo_runner (the true-scratch gate is a DIFFERENT contract than "
        "the committed-scope digest's worktree-reuse optimization)"
    )
