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

Stateless — no memoization. See
docs/feature/fix-des-runtime-interpreter-boundary/feature-delta.md §1.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Literal


Capability = Literal["pytest"]

# Every probe subprocess is bounded by this timeout (R-1). A wedged candidate
# interpreter fails its rung instead of hanging the gate.
_PROBE_TIMEOUT_SECONDS = 10

# The module each capability requires the candidate interpreter to import.
_CAPABILITY_IMPORT: dict[Capability, str] = {"pytest": "pytest"}


class InterpreterUnavailable(RuntimeError):
    """No interpreter on the fallback ladder satisfies the requested capability.

    Raised instead of returning a known-bad interpreter — the boundary refuses
    rather than passing a lie downstream.
    """

    def __init__(self, capability: Capability, probed: list[str]) -> None:
        self.capability = capability
        self.probed = probed
        candidates = ", ".join(probed) if probed else "(none)"
        super().__init__(
            f"no interpreter capable of '{capability}' — probed: {candidates}"
        )


def _candidates() -> list[str]:
    """The fallback ladder of interpreter paths, in priority order.

    1. ``sys.executable`` — the running interpreter (zero-cost common path).
    2. ``uv run python`` — the repo venv interpreter (dev checkout).
    3. a sibling interpreter adjacent to ``sys.executable`` (installed layout
       with a venv python but no uv).
    """
    ladder = [sys.executable]

    uv_python = _uv_python()
    if uv_python:
        ladder.append(uv_python)

    here = Path(sys.executable)
    for sibling_name in ("python", "python3"):
        sibling = here.with_name(sibling_name)
        if str(sibling) not in ladder and sibling.exists():
            ladder.append(str(sibling))

    return ladder


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


def python_for(capability: Capability | None) -> str:
    """Return the path to a Python interpreter that satisfies ``capability``.

    ``capability=None`` returns ``sys.executable`` unconditionally — the
    no-requirement case for callers that only need *a* Python (e.g. ``-m pip``
    or ``-m des.cli.*`` spawns, where the running interpreter already has the
    correct ``des`` visibility).

    ``capability="pytest"`` climbs the fallback ladder, probing each candidate,
    and returns the first interpreter that can import pytest. Raises
    ``InterpreterUnavailable`` if no candidate qualifies — never returns a
    known-bad interpreter.
    """
    if capability is None:
        return sys.executable

    probed: list[str] = []
    for candidate in _candidates():
        probed.append(candidate)
        if _has_capability(candidate):
            return candidate

    raise InterpreterUnavailable(capability, probed)


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
    deduped = [p for p in parts if p and not (p in seen or seen.add(p))]
    env["PYTHONPATH"] = os.pathsep.join(deduped)
    return env


def des_spawn(
    capability: Capability | None,
    *module_args: str,
    script: str | None = None,
    **kw: object,
) -> subprocess.CompletedProcess:
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
    (``des_spawn(cap, "des.cli.roadmap", "--help")`` ->
    ``[python_for(cap), "-m", "des.cli.roadmap", "--help"]``). Pass ``script=``
    for the ``-c <inline-script>`` form (``module_args`` must then be empty).

    Caller kwargs (``cwd``, ``capture_output``, ``text``, ``timeout``,
    ``input``, ``check``, ...) are forwarded unchanged to ``subprocess.run``. A
    caller-supplied ``env`` is MERGED through ``des_subprocess_env(base=env)``
    so the caller's entries are preserved alongside the des root, never dropped.
    """
    base_env = kw.pop("env", None)
    if script is not None:
        argv = [python_for(capability), "-c", script]
    else:
        argv = [python_for(capability), "-m", *module_args]
    return subprocess.run(
        argv,
        env=des_subprocess_env(base=base_env),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )
