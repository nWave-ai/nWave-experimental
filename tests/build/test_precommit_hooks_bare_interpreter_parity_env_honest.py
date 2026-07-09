"""Env-honest companion to ``test_precommit_hooks_bare_interpreter_parity.py``.

Root cause (CI job "Test - Py3.12", 2026-07-08): four ``language: system``
python3 pre-commit hooks import a venv-only third-party dependency (PyYAML,
directly or transitively via ``scripts/docgen.py``) at MODULE LEVEL:

- ``scripts/validation/validate_framework_templates.py`` (``import yaml``)
- ``scripts/validation/validate_yaml_files.py`` (``import yaml``)
- ``scripts/validation/verify_hooks.py`` (``import yaml``)
- ``scripts/hooks/check_documentation_freshness.py`` (execs ``docgen.py``,
  which imports ``yaml``)

Under CI's bare (non-venv) python3, none of these hooks can even load —
``ModuleNotFoundError: yaml`` fires before the hook does any work, and every
push is rejected.

The sibling pin (``test_precommit_hooks_bare_interpreter_parity.py``)
resolves "bare python3" as the first non-venv ``python3`` on PATH. That is
ENV-MASKED: most developer machines have PyYAML installed in the system
site-packages too, so the sibling test PASSES locally and only fails in
CI's pristine interpreter — exactly the defect class that lets this ship.

This module makes the failure deterministic EVERYWHERE by blocking every
import that resolves to a ``site-packages``/``dist-packages`` location (i.e.
anything pip/uv installed into the venv) via a ``sys.meta_path`` finder
BEFORE loading each hook script's module-level code — regardless of what
happens to be installed on the interpreter actually running the subprocess.
Standard-library modules and first-party project modules (e.g.
``scripts.hooks.*``, resolvable straight from the project tree with no venv
involved) are left alone, so only the exact defect class — "needs a
pip-installed dependency merely to load" — is caught, without false-positive
tripping on intra-repo imports. A hook script that needs nothing but the
standard library and its own project tree to load passes; a hook script
that reaches for a venv-installed dependency at import time fails here
exactly as it fails under CI's bare python3 — no reliance on the local
machine's system python3 package set.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.build.test_precommit_hooks_bare_interpreter_parity import (
    _IMPORT_TIMEOUT_SECONDS,
    PROJECT_ROOT,
    _system_python_hook_scripts,
)


#: Marker the blocked-import finder writes to stderr so the assertion
#: messages below can tell "blocked a venv-installed import" apart from any
#: other load-time failure (syntax error, missing file, etc.).
_BLOCKED_IMPORT_MARKER = "BLOCKED_VENV_INSTALLED_IMPORT:"

_DENYLIST_FINDER_PROGRAM = (
    "import sys, importlib.machinery\n"
    "class _DenylistFinder:\n"
    "    def find_spec(self, fullname, path, target=None):\n"
    "        top = fullname.split('.')[0]\n"
    "        if top in sys.stdlib_module_names:\n"
    "            return None\n"
    "        spec = importlib.machinery.PathFinder.find_spec(fullname, path)\n"
    "        if spec is None or not spec.origin:\n"
    "            return None\n"
    "        if 'site-packages' in spec.origin or 'dist-packages' in spec.origin:\n"
    "            raise ModuleNotFoundError(\n"
    f"                {_BLOCKED_IMPORT_MARKER!r} + fullname\n"
    "            )\n"
    "        return None\n"
    "sys.meta_path.insert(0, _DenylistFinder())\n"
)


def _load_with_venv_installed_imports_blocked(
    script: Path,
) -> subprocess.CompletedProcess[str]:
    """Load ``script``'s module-level code under an interpreter that raises
    ``ModuleNotFoundError`` for any import resolving into ``site-packages``/
    ``dist-packages`` (a venv-installed dependency); stdlib and first-party
    project imports resolve normally.

    Runs under ``sys.executable`` (the venv python already running pytest)
    deliberately — the point is blocking venv-installed deps, not choosing
    an interpreter, so this stays deterministic regardless of what a bare
    system ``python3`` happens to have installed on this machine.
    """
    loader_program = (
        _DENYLIST_FINDER_PROGRAM
        + "import importlib.util\n"
        + f"path = {str(script)!r}\n"
        + "spec = importlib.util.spec_from_file_location("
        + "'_hook_parity_env_honest_probe', path)\n"
        + "module = importlib.util.module_from_spec(spec)\n"
        + "sys.modules['_hook_parity_env_honest_probe'] = module\n"
        + "spec.loader.exec_module(module)\n"
    )
    return subprocess.run(
        [sys.executable, "-c", loader_program],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=_IMPORT_TIMEOUT_SECONDS,
    )


@pytest.mark.parametrize(
    "script",
    _system_python_hook_scripts(),
    ids=lambda script: str(script.relative_to(PROJECT_ROOT)),
)
def test_hook_script_loads_with_venv_installed_imports_blocked(script: Path):
    """Module-level code of every system-language python hook script must
    load using only the standard library and the project's own tree — the
    contract CI's bare python3 actually enforces, reproduced here without
    relying on the local machine's system python3 package set."""
    result = _load_with_venv_installed_imports_blocked(script)
    assert result.returncode == 0, (
        f"{script.relative_to(PROJECT_ROOT)} cannot be loaded when "
        f"venv-installed imports are blocked (exit {result.returncode}). "
        f"pre-commit `language: system` hooks run under a bare python3 "
        f"with no venv dependencies available — this script's module-level "
        f"code needs one anyway. Move the third-party import inside the "
        f"function that needs it (lazy import) or drop the dependency for "
        f"module load.\nstderr: {result.stderr}"
    )


@pytest.mark.parametrize(
    "script",
    _system_python_hook_scripts(),
    ids=lambda script: str(script.relative_to(PROJECT_ROOT)),
)
def test_hook_script_must_not_require_blocked_module_to_load(script: Path):
    """Negative-AT: a hook script must NOT require a blocked (venv-only)
    third-party module merely to be LOADED. A module-level import of a
    venv-only dependency is the exact defect this pin exists to catch —
    asserted here by name so the failure diagnostic states which module
    the script wrongly depends on at load time."""
    result = _load_with_venv_installed_imports_blocked(script)
    assert _BLOCKED_IMPORT_MARKER not in result.stderr, (
        f"{script.relative_to(PROJECT_ROOT)} requires a venv-only "
        f"third-party module merely to be loaded — the exact class of "
        f"defect that crashes this hook under pre-commit's bare python3. "
        f"Offending import(s):\n{result.stderr}"
    )
