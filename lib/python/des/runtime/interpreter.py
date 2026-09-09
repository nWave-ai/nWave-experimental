"""des.runtime.interpreter — the canonical Python-interpreter resolution boundary.

Every ``des`` Python-subprocess spawn MUST resolve its interpreter through
``python_for`` rather than trusting ``sys.executable`` inline. F-21 happened
because an installed U2 hook's ``sys.executable`` was a runtime ``python3`` with
``des`` on ``PYTHONPATH`` but no pytest — the code trusted the name, spawned it,
and got ``No module named pytest`` one frame later.

Resolution is **capability-PROBED, never name-trusted**: the returned
interpreter has been verified to import the required module in a throwaway
subprocess. When no candidate on the fallback ladder qualifies, ``python_for``
raises ``InterpreterUnavailable`` — a structured, diagnosable failure at the
boundary — rather than silently returning a known-bad interpreter.

R-1 (normative): every probe subprocess carries an explicit ``timeout``
(``_PROBE_TIMEOUT_SECONDS``). A ``subprocess.TimeoutExpired`` on a rung is
treated identically to a non-zero exit — the rung fails, the ladder advances.
A timeout on the last rung contributes to ``InterpreterUnavailable``, never to a
hang: ``python_for`` runs inside the gate process before any outer
timeout-wrapped subprocess, so an unbounded probe would be a silent no-answer.

MEMOIZED per process, successes only (changed 2026-07-24 — the original design
recorded "Stateless — no memoization" here; see
docs/feature/fix-des-runtime-interpreter-boundary/feature-delta.md §7). That
decision rested on two cost premises, both since measured false: resolution
was assumed to happen "once per gate run" (it happens ~2.7 times per CLI
invocation) at "tens of ms, negligible" (a resolution costs ~200 ms — a 47 ms
``uv run --project`` ladder build plus a 149 ms ``import pytest`` probe, on an
idle box; ~3x that under load). ``python_for`` now caches successful
resolutions keyed by (capability, repo_root, ``VIRTUAL_ENV``) — everything the
answer depends on. Failures are NEVER cached: they raise, so a venv created
after a miss is seen on the next call instead of pinned to a stale negative.
The probe itself is unchanged — capability is still PROBED, never
name-trusted; memoization changes only how often the same question is asked,
never which branch the code takes. Tests clear the cache per test via an
autouse fixture (``clear_resolution_cache``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal


if TYPE_CHECKING:
    from collections.abc import Iterator

from des.runtime.spawn import spawn


Capability = Literal["pytest"]

# Every probe subprocess is bounded by this timeout (R-1). A wedged candidate
# interpreter fails its rung instead of hanging the gate.
_PROBE_TIMEOUT_SECONDS = 10

# The module each capability requires the candidate interpreter to import.
_CAPABILITY_IMPORT: dict[Capability, str] = {"pytest": "pytest"}

# Successful resolutions, keyed by everything the answer depends on:
# the capability, the target repo, and VIRTUAL_ENV (which steers the
# repo-scoped rungs). ONLY successes are stored — a failed resolution raises
# and is never cached, so a venv created after a miss is picked up on the next
# call rather than pinned to a stale negative. Concurrency-safe by
# construction: entries are computed idempotently from read-only probes, so
# two threads racing the same key write the same value.
_RESOLUTION_CACHE: dict[tuple[Capability | None, str | None, str | None], str] = {}


def clear_resolution_cache() -> None:
    """Forget every memoized resolution.

    Production never needs this — a ``des`` process resolves against a fixed
    interpreter landscape and exits. It exists for the test session, which
    drives ``python_for`` thousands of times across mutually-isolated tmp repos
    and monkeypatched ladders in ONE process: the autouse fixture in
    ``tests/conftest.py`` calls this per test so no test can inherit another
    test's resolution.
    """
    _RESOLUTION_CACHE.clear()


class InterpreterUnavailable(RuntimeError):
    """No interpreter on the fallback ladder satisfies the requested capability.

    Raised instead of returning a known-bad interpreter — the boundary refuses
    rather than passing a lie downstream.
    """

    def __init__(
        self,
        capability: Capability,
        probed: list[str],
        *,
        repo_root: Path | None = None,
    ) -> None:
        self.capability = capability
        self.probed = probed
        self.repo_root = repo_root
        candidates = ", ".join(probed) if probed else "(none)"
        if repo_root is None:
            super().__init__(
                f"no interpreter capable of '{capability}' — probed: {candidates}"
            )
            return
        expected_venv = _venv_executable(repo_root / ".venv")
        super().__init__(
            f"no interpreter capable of '{capability}' for repo {repo_root} — "
            f"checked VIRTUAL_ENV (unset, or outside this repo) and the repo's "
            f"own virtualenv at {expected_venv} (not found), then the fallback "
            f"ladder: {candidates}. Create/activate a virtualenv for this repo, "
            f"e.g. `python -m venv {repo_root}/.venv && "
            f"source {repo_root}/.venv/bin/activate && pip install pytest`, "
            "then retry."
        )


def _candidates() -> Iterator[str]:
    """The fallback ladder of interpreter paths, in priority order.

    1. ``sys.executable`` — the running interpreter (zero-cost common path).
    2. ``uv run python`` — the repo venv interpreter (dev checkout).
    3. a sibling interpreter adjacent to ``sys.executable`` (installed layout
       with a venv python but no uv).

    Yielded LAZILY, rung by rung: rung 2 costs a ``uv run --project`` subprocess
    to discover, and rung 1 wins the overwhelming majority of resolutions, so
    building the whole ladder eagerly spent that spawn on every single call and
    threw the answer away. Consuming this as an iterator (never ``[*_candidates()]``)
    pays for a rung only once an earlier rung has actually failed its probe.
    Order is unchanged — this is strictly fewer spawns, never a different answer.
    """
    yielded = [sys.executable]
    yield sys.executable

    uv_python = _uv_python()
    if uv_python and uv_python not in yielded:
        yielded.append(uv_python)
        yield uv_python

    here = Path(sys.executable)
    for sibling_name in ("python", "python3"):
        sibling = here.with_name(sibling_name)
        if str(sibling) not in yielded and sibling.exists():
            yielded.append(str(sibling))
            yield str(sibling)


def _venv_executable(venv_dir: Path) -> Path:
    """Path to the python executable inside a venv directory, cross-platform."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _project_root_for(repo_root: Path) -> Path | None:
    """Walk up from ``repo_root`` to the nearest ancestor with a ``pyproject.toml``.

    The ``repo_root``-scoped counterpart of ``_project_root()``, which anchors
    on THIS module's own ``__file__`` and is therefore blind to which repo a
    caller is targeting (defect #79) — a consumer repo gated by an installed
    ``des`` never shares an ancestor with the installed package's location.
    """
    resolved = repo_root.resolve()
    for ancestor in (resolved, *resolved.parents):
        if (ancestor / "pyproject.toml").is_file():
            return ancestor
    return None


def _repo_scoped_candidates(repo_root: Path) -> list[str]:
    """Candidate interpreters scoped to ``repo_root``, checked BEFORE the
    name-trusted generic ladder (``_candidates()``):

    1. ``VIRTUAL_ENV`` — but ONLY when that virtualenv is rooted inside
       ``repo_root``: never name-trusted merely because it is set — a
       caller's OWN activated venv for an unrelated repo (e.g. the venv
       ``des`` itself is running under) must not leak into another repo's
       resolution.
    2. ``<nearest pyproject.toml ancestor of repo_root>/.venv/bin/python``.

    Existence-filtered only — capability is PROBED uniformly by the caller
    (``python_for``), never trusted here just because a path exists.
    """
    candidates: list[str] = []

    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        venv_root = Path(virtual_env).resolve()
        if venv_root.is_relative_to(repo_root.resolve()):
            venv_python = _venv_executable(venv_root)
            if venv_python.is_file():
                candidates.append(str(venv_python))

    project_root = _project_root_for(repo_root)
    if project_root is not None:
        venv_python = _venv_executable(project_root / ".venv")
        candidate_str = str(venv_python)
        if venv_python.is_file() and candidate_str not in candidates:
            candidates.append(candidate_str)

    return candidates


def _project_root() -> Path | None:
    """Walk up from this module to the nearest ancestor with a ``pyproject.toml``.

    The dev checkout lives under ``<root>/src/des/runtime/interpreter.py`` with
    ``<root>/pyproject.toml`` + ``<root>/.venv``. Returns None in the installed
    standalone layout (no ``pyproject.toml`` ancestor), where rung 2 does not
    apply and the ladder advances to the sibling rung.
    """
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / "pyproject.toml").is_file():
            return ancestor
    return None


def _uv_python() -> str | None:
    """Resolve the repo venv interpreter via ``uv run``, or None if uv is absent,
    the probe times out, or no project root is found.

    NO-LITTER CONTRACT: the probe runs ``uv run --project <root>`` so it resolves
    the repo's ``.venv`` regardless of the caller's cwd, and writes nothing into
    the caller's cwd. (The predecessor ``pipenv run`` auto-created an empty
    ``Pipfile`` in cwd — when the gate ran with ``cwd=<tmp-repo>`` that littered
    the repo under test. ``--project`` makes resolution cwd-independent, so no
    file is ever dropped into the probe's cwd.)
    """
    root = _project_root()
    if root is None:
        return None
    try:
        resolved = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(root),
                "python",
                "-c",
                "import sys; print(sys.executable)",
            ],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    candidate = resolved.stdout.strip()
    return candidate or None


def _probe(interpreter: str) -> subprocess.CompletedProcess[str]:
    """Run ``interpreter -c "import pytest"`` bounded by the probe timeout."""
    return subprocess.run(
        [interpreter, "-c", "import pytest"],
        capture_output=True,
        text=True,
        timeout=_PROBE_TIMEOUT_SECONDS,
    )


def _has_capability(interpreter: str) -> bool:
    """True iff ``interpreter`` can import the pytest capability module.

    A ``TimeoutExpired`` (a wedged candidate) is treated identically to a
    non-zero exit — the rung is failed, not hung (R-1).
    """
    try:
        return _probe(interpreter).returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        return False


def can_import(interpreter: str, module: str) -> bool:
    """True iff ``interpreter`` can import ``module`` (probed, never name-trusted).

    A capability probe for an OPTIONAL module — unlike ``python_for``, the
    caller decides what to do on a ``False`` (e.g. degrade to serial when
    ``pytest-xdist`` is absent), so this never raises. A wedged candidate
    (``TimeoutExpired``) or a missing binary (``FileNotFoundError``) both
    answer ``False`` rather than hang or crash the boundary (R-1).
    """
    try:
        return (
            subprocess.run(
                [interpreter, "-c", f"import {module}"],
                capture_output=True,
                text=True,
                timeout=_PROBE_TIMEOUT_SECONDS,
            ).returncode
            == 0
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def python_for(capability: Capability | None, repo_root: Path | None = None) -> str:
    """Return the path to a Python interpreter that satisfies ``capability``.

    ``capability=None`` and ``repo_root=None`` returns ``sys.executable``
    unconditionally — the no-requirement case for callers that only need *a*
    Python (e.g. ``-m pip`` or ``-m des.cli.*`` spawns, where the running
    interpreter already has the correct ``des`` visibility).

    ``capability="pytest"`` climbs the fallback ladder, probing each candidate,
    and returns the first interpreter that can import pytest. Raises
    ``InterpreterUnavailable`` if no candidate qualifies — never returns a
    known-bad interpreter.

    ``repo_root``, when given, steers resolution at the TARGET repo being
    gated rather than the installed ``des`` package's own location (defect
    #79 — ``_project_root()``/``_uv_python()`` anchor on this module's own
    ``__file__``, never the caller's target). The repo-scoped rungs
    (``VIRTUAL_ENV`` when rooted inside ``repo_root``, then
    ``<repo_root>/.venv/bin/python``) are probed BEFORE the existing
    name-trusted ladder, which stays as a later fallback rung — so
    ``repo_root`` naming this repo's own checkout (the dogfood self-gate
    path) resolves byte-identically to the no-``repo_root`` call. A
    ``capability=None`` request with a ``repo_root`` still prefers the
    repo-scoped venv over the running interpreter (the E2 contract-gate
    route), since the fallback ladder always yields at least
    ``sys.executable`` the request can never go unsatisfied.
    """
    if capability is None and repo_root is None:
        return sys.executable

    cache_key = (
        capability,
        str(repo_root.resolve()) if repo_root is not None else None,
        os.environ.get("VIRTUAL_ENV"),
    )
    cached = _RESOLUTION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    ladder = chain(
        _repo_scoped_candidates(repo_root) if repo_root is not None else (),
        _candidates(),
    )

    probed: list[str] = []
    for candidate in ladder:
        if candidate in probed:
            continue
        probed.append(candidate)
        if capability is None or _has_capability(candidate):
            _RESOLUTION_CACHE[cache_key] = candidate
            return candidate

    # capability is never None here: a None capability always matches the
    # first rung (the ladder is never empty — _candidates() always yields
    # sys.executable first), so only a real capability requirement reaches
    # this raise.
    assert capability is not None
    raise InterpreterUnavailable(capability, probed, repo_root=repo_root)


def _des_root() -> str:
    """The directory CONTAINING the ``des`` package (so ``import des`` resolves).

    ``interpreter.py`` lives at ``<root>/des/runtime/interpreter.py`` -- in the dev
    checkout ``<root>`` is ``src/``; in the installed standalone layout it is
    ``~/.claude/lib/python``. ``parents[2]`` is that containing dir either way.
    """
    return str(Path(__file__).resolve().parents[2])


def des_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Env for a ``des.cli`` subprocess spawn, with ``des`` guaranteed on PYTHONPATH.

    F-DES-SUBPROCESS-PYTHONPATH-PROPAGATION: ``python_for(None)`` returns the
    running interpreter, but a child subprocess does NOT inherit the parent's
    *runtime* ``sys.path`` -- e.g. the installed shim's ``sys.path.insert`` of
    ``~/.claude/lib/python`` is a runtime insertion, not an env var. So a spawned
    ``des.cli`` child process raises ``ModuleNotFoundError: des`` unless ``des``'s
    containing directory is on ``PYTHONPATH`` -- an env var children DO inherit.
    This prepends ``_des_root()`` to PYTHONPATH (de-duplicated, order-preserving)
    so every des subprocess can import des regardless of how the parent acquired
    it (shim sys.path.insert, dev `src` layout, or installed site).
    """
    env = dict(os.environ if base is None else base)
    existing = env.get("PYTHONPATH", "")
    parts = [_des_root(), *(existing.split(os.pathsep) if existing else [])]
    seen: set[str] = set()
    deduped: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            deduped.append(p)
    env["PYTHONPATH"] = os.pathsep.join(deduped)
    return env


def des_spawn(
    capability: Capability | None,
    *module_args: str,
    script: str | None = None,
    **kw: Any,
) -> subprocess.CompletedProcess[Any]:
    """The single boundary that spawns a ``des`` Python subprocess.

    Composes the two interpreter primitives BY CONSTRUCTION so no caller can
    forget either: argv[0] is ``python_for(capability)`` (the probed, never
    name-trusted interpreter) and ``env`` is ``des_subprocess_env(base=...)``
    (``des`` guaranteed on the child ``PYTHONPATH``). Every ``des``-module
    subprocess spawn in ``src/des/**`` routes through here — the
    ``test_no_inline_des_module_spawn`` arch-ban makes a bypassing inline spawn
    fail the build, so the F-DES-SUBPROCESS-PYTHONPATH null-``Gate-Scope``
    false-DONE (a child that lost ``des`` from its path) cannot recur.

    By default the child runs ``-m <module> <args...>``
    (``des_spawn(cap, "des.cli.health_check", "--help")`` ->
    ``[python_for(cap), "-m", "des.cli.health_check", "--help"]``). Pass ``script=``
    for the ``-c <inline-script>`` form (``module_args`` must then be empty).

    Caller kwargs (``cwd``, ``capture_output``, ``text``, ``timeout``,
    ``input``, ``check``, ...) are forwarded unchanged. A caller-supplied ``env``
    is MERGED through ``des_subprocess_env(base=env)`` so the caller's entries are
    preserved alongside the des root, never dropped.

    The actual process creation is DELEGATED to ``des.runtime.spawn.spawn`` (RCA
    ``fix-inherited-stdin-deadlocks-spawns`` §7/§9.2): this function keeps its own
    duties — interpreter resolution and ``PYTHONPATH`` — and the boundary one
    level lower owns the three every spawn needs (an explicit stdin, a bound,
    a reaped process group). Every one of this function's call sites inherits
    those for free; the selection criteria are orthogonal, which is why the
    boundary is a separate object and not an extension of this one.
    """
    base_env = kw.pop("env", None)
    if script is not None:
        argv = [python_for(capability), "-c", script]
    else:
        argv = [python_for(capability), "-m", *module_args]
    return spawn(
        argv,
        env=des_subprocess_env(base=base_env),
        **kw,
    )
