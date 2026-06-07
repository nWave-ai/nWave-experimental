"""Layer B arch test — ``python_for`` proven under a pytest-LESS interpreter
(S1, feature-delta §3 Layer B — the non-tautological half).

Layer A (``test_no_inline_interpreter_spawn.py``) proves no inline spawn exists
in source, but it runs under the dev interpreter, which HAS pytest — it cannot
exercise the pytest-less path. This test constructs a pytest-less interpreter at
runtime and proves the helper still resolves a pytest-capable one.

Mechanism (not a mock — the subprocess IS the system under test):
  1. Build a throwaway venv via ``python -m venv`` in ``tmp_path``. A fresh
     venv has NO pytest.
  2. Spawn ``[<pytestless_venv_python>, "-c", "...python_for('pytest')..."]``
     with ``PYTHONPATH`` pointing at ``src/`` so ``des`` is importable but
     pytest is not — the exact installed-runtime closure that caused F-21.
  3. Assert exit 0 AND the printed path, when probed, can ``import pytest`` —
     i.e. the helper, running under a pytest-less interpreter, climbed its
     fallback ladder to a pytest-capable one.
  4. Negative case: spawn a one-liner that sabotages the ladder (every
     candidate forced to a non-existent path) and assert ``python_for`` raises
     ``InterpreterUnavailable`` — exit non-zero, structured message — proving
     the boundary refuses rather than silently returning ``sys.executable``.

Single-worker note (residuality R-2b): this test builds exactly ONE venv. It is
not parameterized — one venv build, not one-per-xdist-worker — so the
filesystem-heavy ``venv`` creation does not multiply under xdist.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

# Generous ceiling — venv creation + probe ladder. Bounds a hung build.
_BUILD_TIMEOUT_SECONDS = 120


def _env_with_src_on_pythonpath() -> dict[str, str]:
    """Inherit the real environment (PATH must survive so the helper's pipenv
    and sibling-interpreter rungs can resolve) and overlay PYTHONPATH so the
    pytest-less venv can import the `des` package."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    return env


def _venv_python(venv_dir: Path) -> Path:
    """Path to the python executable inside a freshly-built venv."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


@pytest.fixture(scope="module")
def pytestless_python(tmp_path_factory) -> Path:
    """A freshly-built venv interpreter with no pytest installed.

    Module-scoped: exactly one venv build for the whole module (R-2b — the
    venv build does not multiply per test function).
    """
    venv_dir = tmp_path_factory.mktemp("pytestless_venv") / "venv"
    venv.create(venv_dir, with_pip=False, clear=True)
    interpreter = _venv_python(venv_dir)
    assert interpreter.is_file(), f"venv python not created at {interpreter}"

    # Sanity: the freshly-built venv genuinely lacks pytest — this reproduces
    # the F-21 installed-runtime closure.
    probe = subprocess.run(
        [str(interpreter), "-c", "import pytest"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode != 0, (
        "fixture invariant broken: the throwaway venv unexpectedly HAS pytest "
        "— Layer B would be tautological"
    )
    return interpreter


@pytest.mark.integration
def test_python_for_climbs_ladder_under_pytestless_host(pytestless_python: Path):
    """``python_for('pytest')`` resolves a pytest-capable interpreter even when
    the running process itself lacks pytest (R-2: single-worker venv build).

    The helper executes UNDER the pytest-less venv interpreter; if it regressed
    to trusting ``sys.executable`` it would return the pytest-less venv and the
    capability probe in step 4 would fail.
    """
    one_liner = (
        "from des.runtime.interpreter import python_for; print(python_for('pytest'))"
    )
    result = subprocess.run(
        [str(pytestless_python), "-c", one_liner],
        capture_output=True,
        text=True,
        env=_env_with_src_on_pythonpath(),
        timeout=_BUILD_TIMEOUT_SECONDS,
    )

    assert result.returncode == 0, (
        f"python_for('pytest') failed under a pytest-less host "
        f"(exit {result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    resolved = result.stdout.strip()
    assert resolved, "python_for('pytest') printed no interpreter path"

    # The resolved interpreter must actually be pytest-capable — proving the
    # ladder climbed away from the pytest-less host, not just returned it.
    capability_probe = subprocess.run(
        [resolved, "-c", "import pytest"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert capability_probe.returncode == 0, (
        f"python_for('pytest') returned {resolved!r} but it cannot import "
        f"pytest — the helper did not climb its fallback ladder.\n"
        f"stderr: {capability_probe.stderr}"
    )


@pytest.mark.integration
def test_python_for_raises_when_ladder_sabotaged(pytestless_python: Path):
    """``python_for('pytest')`` raises ``InterpreterUnavailable`` — exit
    non-zero, structured message — when every candidate on the ladder fails.

    Proves the boundary REFUSES rather than silently returning a known-bad
    ``sys.executable`` (the F-21 deferred-crash failure mode).
    """
    # Sabotage: replace the ladder with a single non-existent interpreter.
    # `_has_capability` catches FileNotFoundError -> rung fails -> ladder
    # exhausts -> InterpreterUnavailable is raised. A multi-line try/except is
    # passed via a module file (a `-c` one-liner cannot carry a statement
    # block), written into tmp_path alongside the venv.
    sabotage_program = "\n".join(
        [
            "import sys",
            "import des.runtime.interpreter as mod",
            "mod._candidates = lambda: ['/nonexistent/python-sabotaged']",
            "from des.runtime.interpreter import (",
            "    python_for,",
            "    InterpreterUnavailable,",
            ")",
            "try:",
            "    python_for('pytest')",
            "    sys.exit(0)",
            "except InterpreterUnavailable as exc:",
            "    print('INTERPRETER_UNAVAILABLE:' + str(exc))",
            "    sys.exit(3)",
        ]
    )
    program_path = pytestless_python.parent.parent / "sabotage_program.py"
    program_path.write_text(sabotage_program, encoding="utf-8")
    result = subprocess.run(
        [str(pytestless_python), str(program_path)],
        capture_output=True,
        text=True,
        env=_env_with_src_on_pythonpath(),
        timeout=_BUILD_TIMEOUT_SECONDS,
    )

    assert result.returncode != 0, (
        "python_for('pytest') did NOT raise on a sabotaged ladder — the "
        "boundary silently returned an interpreter instead of refusing.\n"
        f"stdout: {result.stdout}"
    )
    assert "INTERPRETER_UNAVAILABLE:" in result.stdout, (
        "expected a structured InterpreterUnavailable message on a sabotaged "
        f"ladder.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "pytest" in result.stdout, (
        "InterpreterUnavailable message must name the unsatisfied capability "
        f"('pytest').\nstdout: {result.stdout}"
    )
