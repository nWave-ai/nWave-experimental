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
    2. ``pipenv run python`` — the repo venv interpreter (dev checkout).
    3. a sibling interpreter adjacent to ``sys.executable`` (installed layout
       with a venv python but no pipenv).
    """
    ladder = [sys.executable]

    pipenv_python = _pipenv_python()
    if pipenv_python:
        ladder.append(pipenv_python)

    here = Path(sys.executable)
    for sibling_name in ("python", "python3"):
        sibling = here.with_name(sibling_name)
        if str(sibling) not in ladder and sibling.exists():
            ladder.append(str(sibling))

    return ladder


def _pipenv_python() -> str | None:
    """Resolve ``pipenv run python``'s ``sys.executable``, or None if pipenv is
    absent or the resolution probe times out."""
    try:
        resolved = subprocess.run(
            ["pipenv", "run", "python", "-c", "import sys; print(sys.executable)"],
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
