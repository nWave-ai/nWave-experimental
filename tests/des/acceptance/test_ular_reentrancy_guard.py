"""Acceptance tests -- ULAR re-entrancy guard (DISTILL, slice-01, `@infrastructure`).

Feature-delta: docs/feature/ular-reentrancy-guard/feature-delta.md
Design SSOT:   docs/feature/unified-language-adapter-registry/design/adrs/
               ADR-ULAR-004-reentrancy-guard-repo-scoped-env-sentinel.md

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/adapters/driven/runner/reentrancy_guard.py` (C14), stdlib-only:
  - `is_routing_active_for(repo: Path) -> bool` -- True iff the repo-path-scoped
    sentinel marks routing active for `str(repo.resolve())`; False otherwise
    (incl. a different target).
  - `routing_active_for(repo: Path)` -- a context manager setting the sentinel
    on entry and RESTORING the prior state on exit (including when the body
    raises). Keyed on `str(repo.resolve())`.
  - Sentinel = env var `NWAVE_LANG_ADAPTER_ROUTE_ACTIVE`, so a child process
    inheriting the environment observes active routing with zero propagation
    code (the design's whole point).

This is a guard-first `@infrastructure` slice (feature-delta charter-governance
rule 4): no user-observable value, no expectation charter -- the reviewer
audit (C_REVIEWER_AUDIT) is this slice's audit; EXAMINE is unarmed by design.
The seam wiring (C5/C6/C7) + entry-point registration is a DEFERRED later
slice; this slice ships the guard module ALONE.

Active-RED scaffolding (P1-P4, `nw-distill-red-scaffolding`): the module is
absent today, so the import happens INSIDE a helper called from each test
body (hidden-import), never at module top -- collection stays green
(COLLECT >= 10) and the absence surfaces as a semantic AssertionError
(MISSING_FUNCTIONALITY) at runtime, never a collection ImportError (BROKEN).

Driving surface (Mandate-13 driving-port-only): the guard is itself the C14
production module (not fronted by a CLI in this slice) -- scenarios 1-6 drive
it directly, in-process; scenario 7 drives a REAL child `python -c` subprocess
to prove the env-sentinel's cross-process visibility, the one claim that
cannot be witnessed in-process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


_GUARD_ENV_VAR = "NWAVE_LANG_ADAPTER_ROUTE_ACTIVE"


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3): keep the absent module out of collection
# scope; the absence surfaces as a runtime AssertionError inside a test body.
# ---------------------------------------------------------------------------


def _import_guard():
    try:
        from des.adapters.driven.runner import reentrancy_guard
    except ImportError as exc:
        # `des.adapters.driven.runner` is an existing package, so the absent
        # `reentrancy_guard` submodule surfaces as a plain `ImportError`
        # ("cannot import name ... from ..."), not `ModuleNotFoundError` --
        # catch the broader class (ModuleNotFoundError is a subclass of it).
        raise AssertionError(
            "MISSING_FUNCTIONALITY: "
            "src/des/adapters/driven/runner/reentrancy_guard.py does not "
            f"exist yet ({exc}). Implement `is_routing_active_for(repo)` + "
            "`routing_active_for(repo)` per ADR-ULAR-004 (repo-scoped env "
            "sentinel `NWAVE_LANG_ADAPTER_ROUTE_ACTIVE`) before this AT can "
            "pass."
        ) from exc
    return reentrancy_guard


# ---------------------------------------------------------------------------
# Env hygiene -- the module under test manipulates os.environ directly (not
# via monkeypatch), so a RED-phase bug (leaked sentinel) must not bleed into
# the next test in this process. Clean before AND after every test.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_guard_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(_GUARD_ENV_VAR, raising=False)
    yield
    monkeypatch.delenv(_GUARD_ENV_VAR, raising=False)


def _repo_root() -> Path:
    """tests/des/acceptance/<file> -> parents[3] = REPO_ROOT."""
    return Path(__file__).resolve().parents[3]


def _child_env() -> dict[str, str]:
    """Real process env (carries whatever sentinel is currently active) plus
    a defensive PYTHONPATH so `des` resolves even off an editable install."""
    env = dict(os.environ)
    root = _repo_root()
    src = str(root / "src")
    existing = env.get("PYTHONPATH", "")
    prepend = src + os.pathsep + str(root)
    env["PYTHONPATH"] = prepend + os.pathsep + existing if existing else prepend
    return env


# ---------------------------------------------------------------------------
# Scenario 1 -- inactive by default
# ---------------------------------------------------------------------------
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_is_routing_active_for_returns_false_by_default(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    With no `routing_active_for` context ever entered, the sentinel is
    absent, so a fresh repo path reads as inactive.
    """
    guard = _import_guard()
    repo = tmp_path / "repo-a"
    repo.mkdir()

    assert guard.is_routing_active_for(repo) is False, (
        "expected inactive-by-default with no sentinel set"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- active in-context, same target
# ---------------------------------------------------------------------------
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_is_routing_active_for_returns_true_inside_context_for_same_target(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    Inside `routing_active_for(repo)`, querying the SAME repo path reports
    active.
    """
    guard = _import_guard()
    repo = tmp_path / "repo-a"
    repo.mkdir()

    with guard.routing_active_for(repo):
        assert guard.is_routing_active_for(repo) is True, (
            "expected active-in-context for the same target repo"
        )


# ---------------------------------------------------------------------------
# Scenario 3 -- NOT active for a different target (never false-blocks a
# legitimately nested, different call)
# ---------------------------------------------------------------------------
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_is_routing_active_for_returns_false_for_a_different_target(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    Inside the same block, a DIFFERENT target repo must never read as
    active -- the guard is precise (repo-path-scoped), not a bare boolean,
    so it never false-blocks a legitimately nested, different-target call.
    """
    guard = _import_guard()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    with guard.routing_active_for(repo_a):
        assert guard.is_routing_active_for(repo_b) is False, (
            "a different target repo must never read as active while the "
            "guard is held for another repo"
        )


@pytest.mark.parametrize(
    "alias_relpath",
    [".", "sub/..", "./sub/.."],
    ids=["dot", "sub-dotdot", "dot-sub-dotdot"],
)
def test_is_routing_active_for_treats_path_equivalent_alias_as_same_target(
    tmp_path: Path, alias_relpath: str
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    The guard is keyed on `str(repo.resolve())`, so a path-equivalent alias
    of the SAME repo (e.g. `repo_a / "."`) IS the same target -- resolving
    identically, never treated as a different, non-blocked repo.
    """
    guard = _import_guard()
    repo_a = tmp_path / "repo-a"
    (repo_a / "sub").mkdir(parents=True)
    alias = repo_a / alias_relpath

    with guard.routing_active_for(repo_a):
        assert guard.is_routing_active_for(alias) is True, (
            f"path-equivalent alias {alias} must resolve to the same target "
            f"as {repo_a} and read as active"
        )


# ---------------------------------------------------------------------------
# Scenario 4 -- restored on exit, including when the body raises
# ---------------------------------------------------------------------------
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_routing_active_for_restores_prior_state_on_normal_exit(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    After a normal (non-raising) exit from `routing_active_for(repo)`, the
    prior (inactive) state is restored.
    """
    guard = _import_guard()
    repo = tmp_path / "repo-a"
    repo.mkdir()

    with guard.routing_active_for(repo):
        assert guard.is_routing_active_for(repo) is True

    assert guard.is_routing_active_for(repo) is False, (
        "expected the prior inactive state restored after a normal exit"
    )


@pytest.mark.negative_at
def test_guard_does_not_leak_active_state_after_exception(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    Negative AT (GS-8): asserts the WRONG outcome -- a leaked-active sentinel
    after the guarded body raises -- is NOT produced. A leaked sentinel would
    permanently, silently false-block every later, legitimate call against
    the same repo (the exact staleness failure mode ADR-ULAR-004 rejects the
    marker-file-lock alternative for).
    """
    guard = _import_guard()
    repo = tmp_path / "repo-a"
    repo.mkdir()

    class _FixtureBoom(Exception):
        pass

    with pytest.raises(_FixtureBoom):
        with guard.routing_active_for(repo):
            assert guard.is_routing_active_for(repo) is True
            raise _FixtureBoom("body raised mid-guard")

    assert guard.is_routing_active_for(repo) is False, (
        "the guard must NOT leak active state after the guarded body raises "
        "-- a leaked sentinel would false-block a later, legitimate call "
        "against the same repo"
    )


# ---------------------------------------------------------------------------
# Scenario 5 -- sentinel visible across processes (stdlib env-inheritance,
# zero propagation code -- the design's whole point)
# ---------------------------------------------------------------------------
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_sentinel_visible_to_child_subprocess_via_env_inheritance(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    A REAL child `python -c` process, spawned while `routing_active_for` is
    held, observes the sentinel via ordinary `subprocess.run` env-inheritance
    -- no propagation code required. This is the design's whole point: any
    descendant process (including a nested `des` invocation) sees the
    active-routing state for free.
    """
    guard = _import_guard()
    repo = tmp_path / "repo-a"
    repo.mkdir()

    program = textwrap.dedent(
        f"""\
        import importlib
        from pathlib import Path
        guard_mod = importlib.import_module(
            "des.adapters.driven.runner.reentrancy_guard"
        )
        active = guard_mod.is_routing_active_for(Path({str(repo)!r}))
        print("ACTIVE:" + str(active))
        """
    )

    with guard.routing_active_for(repo):
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            check=False,
            env=_child_env(),
        )

    assert "ACTIVE:True" in completed.stdout, (
        "expected the child subprocess to observe the sentinel via inherited "
        f"env; stdout={completed.stdout!r} stderr={completed.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 6 -- nested composition: a DIFFERENT-target nested guard unwinds
# without disturbing the outer guard's still-active state (ADR-ULAR-004
# Consequences: "nesting a call for a different repo composes safely").
# ---------------------------------------------------------------------------
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_routing_active_for_composes_safely_when_nested_for_a_different_target(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch (guard-first `@infrastructure`
    slice -- no DISCUSS charter; ADR-ULAR-004 is the design SSOT; elevator
    pitch: "the guard reports routing-active only for the same target repo").

    Entering `routing_active_for(repo_a)` with no prior sentinel, then
    NESTING `routing_active_for(repo_b)` inside it and exiting the inner
    context, must restore exactly repo_a's still-active state -- not wipe
    the sentinel outright. A naive `finally: os.environ.pop(VAR, None)`
    (discarding the captured prior instead of restoring it) would pass
    every OTHER AT in this file, since each of them opens only ONE `with`
    block -- this scenario is the one that pins the composition guarantee.
    """
    guard = _import_guard()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    with guard.routing_active_for(repo_a):
        with guard.routing_active_for(repo_b):
            assert guard.is_routing_active_for(repo_a) is True
            assert guard.is_routing_active_for(repo_b) is True

        assert guard.is_routing_active_for(repo_a) is True, (
            "exiting the INNER (different-target) guard must not disturb "
            "the OUTER guard's still-active state"
        )
        assert guard.is_routing_active_for(repo_b) is False, (
            "exiting the INNER guard must deactivate its own target"
        )

    assert guard.is_routing_active_for(repo_a) is False, (
        "exiting the OUTER guard must restore the true prior (absent) state"
    )
    assert guard.is_routing_active_for(repo_b) is False
