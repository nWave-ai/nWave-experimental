"""Unit tests for des.runtime.interpreter.python_for — step 01-01.

RED-authored example-based unit tests (no DISTILL AT scaffold exists for this
feature). Covers the four acceptance criteria of step 01-01:

  AC-1  python_for("pytest") under a pytest-less interpreter returns a
        pytest-capable interpreter path (a later rung wins).
  AC-2  python_for(None) returns sys.executable unconditionally.
  AC-3  no candidate satisfies the capability -> raises InterpreterUnavailable
        listing the probed candidates; never returns a known-bad interpreter.
  AC-4  R-1 — a probe rung that hangs is demoted within _PROBE_TIMEOUT_SECONDS;
        the ladder advances or raises, python_for never hangs.

The input domain is a tiny Literal + ladder state; per the design (§6) PBT is
not warranted — example-based per-rung is the right shape.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from des.runtime.interpreter import (
    _PROBE_TIMEOUT_SECONDS,
    InterpreterUnavailable,
    can_import,
    des_subprocess_env,
    python_for,
)


# --------------------------------------------------------------------------
# AC-2 — the None path: sys.executable unconditionally, no probing.
# --------------------------------------------------------------------------
def test_python_for_none_returns_sys_executable_unconditionally(monkeypatch):
    """python_for(None) returns sys.executable without probing any rung."""

    def _fail_if_probed(*_args, **_kwargs):  # pragma: no cover - must not run
        raise AssertionError("python_for(None) must not probe interpreters")

    monkeypatch.setattr("des.runtime.interpreter._has_capability", _fail_if_probed)

    assert python_for(None) == sys.executable


# --------------------------------------------------------------------------
# AC-1 rung 1 — sys.executable already pytest-capable: zero-cost path.
# --------------------------------------------------------------------------
def test_python_for_pytest_returns_running_interpreter_when_capable(monkeypatch):
    """When sys.executable can import pytest, rung 1 wins — no later rung."""
    probed: list[str] = []

    def _capable(interpreter: str) -> bool:
        probed.append(interpreter)
        return interpreter == sys.executable

    monkeypatch.setattr("des.runtime.interpreter._has_capability", _capable)

    assert python_for("pytest") == sys.executable
    assert probed == [sys.executable]


# --------------------------------------------------------------------------
# AC-1 later rung — sys.executable pytest-LESS, a fallback rung qualifies.
# --------------------------------------------------------------------------
def test_python_for_pytest_climbs_to_later_rung_when_running_interpreter_lacks_pytest(
    monkeypatch,
):
    """Run under a pytest-less interpreter: the ladder advances and a later
    rung's pytest-capable interpreter is returned."""
    fallback = "/opt/venv/bin/python"

    monkeypatch.setattr(
        "des.runtime.interpreter._candidates",
        lambda: [sys.executable, fallback],
    )

    def _capable(interpreter: str) -> bool:
        return interpreter == fallback

    monkeypatch.setattr("des.runtime.interpreter._has_capability", _capable)

    assert python_for("pytest") == fallback


# --------------------------------------------------------------------------
# AC-3 — no candidate qualifies: raise, never return a known-bad interpreter.
# --------------------------------------------------------------------------
def test_python_for_pytest_raises_when_no_candidate_qualifies(monkeypatch):
    """Every rung fails the capability probe -> InterpreterUnavailable listing
    the probed candidates; python_for must not return sys.executable."""
    candidates = [sys.executable, "/opt/venv/bin/python"]
    monkeypatch.setattr("des.runtime.interpreter._candidates", lambda: candidates)
    monkeypatch.setattr(
        "des.runtime.interpreter._has_capability", lambda _interp: False
    )

    with pytest.raises(InterpreterUnavailable) as exc_info:
        python_for("pytest")

    message = str(exc_info.value)
    assert "pytest" in message
    for candidate in candidates:
        assert candidate in message


# --------------------------------------------------------------------------
# AC-4 / R-1 — a hanging probe rung is demoted within the timeout; the ladder
# still advances. python_for never hangs.
# --------------------------------------------------------------------------
def test_python_for_pytest_demotes_hanging_rung_and_advances(monkeypatch):
    """A rung whose probe subprocess wedges (TimeoutExpired) is treated as a
    failed rung; the ladder advances to the next rung and resolves."""
    hanging = "/wedged/python"
    healthy = "/opt/venv/bin/python"
    monkeypatch.setattr(
        "des.runtime.interpreter._candidates",
        lambda: [hanging, healthy],
    )

    def _probe(interpreter: str) -> subprocess.CompletedProcess[str]:
        if interpreter == hanging:
            raise subprocess.TimeoutExpired(
                cmd=[interpreter, "-c", "import pytest"],
                timeout=_PROBE_TIMEOUT_SECONDS,
            )
        return subprocess.CompletedProcess(
            args=[interpreter], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("des.runtime.interpreter._probe", _probe)

    assert python_for("pytest") == healthy


def test_python_for_pytest_raises_when_last_rung_hangs(monkeypatch):
    """A timeout on the last rung contributes to InterpreterUnavailable —
    never to a hang."""
    only = "/wedged/python"
    monkeypatch.setattr("des.runtime.interpreter._candidates", lambda: [only])

    def _probe(interpreter: str) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=[interpreter, "-c", "import pytest"],
            timeout=_PROBE_TIMEOUT_SECONDS,
        )

    monkeypatch.setattr("des.runtime.interpreter._probe", _probe)

    with pytest.raises(InterpreterUnavailable):
        python_for("pytest")


# --------------------------------------------------------------------------
# can_import — the OPTIONAL-module capability probe (xdist parallel-RUN seam).
# --------------------------------------------------------------------------
def test_can_import_true_for_stdlib_module():
    """A module the running interpreter can import probes True (real subprocess)."""
    assert can_import(sys.executable, "sys") is True


def test_can_import_false_for_nonexistent_module():
    """A bogus module name probes False — never raises (caller-decides contract)."""
    assert can_import(sys.executable, "this_module_does_not_exist_zzz") is False


def test_can_import_false_on_missing_interpreter_binary():
    """A missing interpreter binary answers False, not FileNotFoundError (R-1)."""
    assert can_import("/no/such/python/binary", "sys") is False


def test_can_import_false_on_probe_timeout(monkeypatch):
    """A wedged probe is demoted to False within the boundary, never hangs (R-1)."""

    def _wedged(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["python"], timeout=_PROBE_TIMEOUT_SECONDS)

    monkeypatch.setattr("des.runtime.interpreter.subprocess.run", _wedged)
    assert can_import(sys.executable, "sys") is False


# --------------------------------------------------------------------------
# F-DES-SUBPROCESS-PYTHONPATH-PROPAGATION — des_subprocess_env() guarantees a
# spawned des.cli subprocess can import des even on an interpreter without des
# natively (the installed-shim /usr/bin/python3 case: des reached only via the
# parent's runtime sys.path.insert, which children do NOT inherit).
# --------------------------------------------------------------------------
def test_des_subprocess_env_prepends_des_root_to_pythonpath(monkeypatch):
    """des_subprocess_env puts des's containing dir FIRST on PYTHONPATH, de-duped."""

    from des.runtime.interpreter import _des_root

    monkeypatch.setenv("PYTHONPATH", f"/existing/a{os.pathsep}{_des_root()}")
    env = des_subprocess_env()
    parts = env["PYTHONPATH"].split(os.pathsep)
    assert parts[0] == _des_root()  # des root wins
    assert parts.count(_des_root()) == 1  # de-duped
    assert "/existing/a" in parts  # existing entries preserved


def test_des_subprocess_env_makes_des_importable_under_pytestless_site():
    """REGRESSION: a `-S` interpreter (no site-packages, simulating the shim's
    /usr/bin/python3 where des is not natively installed) cannot import des with
    a cleared PYTHONPATH, but CAN with des_subprocess_env() — proving the env
    propagation fixes the ModuleNotFoundError: des the gate subprocesses hit."""

    # Reproduce the bug: -S disables site (so the .pth editable des is invisible),
    # cleared PYTHONPATH -> des unreachable.
    clean = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    broken = subprocess.run(
        [sys.executable, "-S", "-c", "import des"],
        env=clean,
        capture_output=True,
        text=True,
    )
    assert broken.returncode != 0, "guard: -S + no PYTHONPATH must NOT find des"

    # The fix: des_subprocess_env() restores des-visibility via PYTHONPATH.
    fixed = subprocess.run(
        [sys.executable, "-S", "-c", "import des"],
        env=des_subprocess_env(clean),
        capture_output=True,
        text=True,
    )
    assert fixed.returncode == 0, (
        f"des_subprocess_env must make des importable: {fixed.stderr}"
    )
