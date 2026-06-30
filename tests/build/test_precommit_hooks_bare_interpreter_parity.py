"""Interpreter-parity pin for ``language: system`` python pre-commit hooks.

Root cause class (pre-push hook repair, 2026-06-11): hooks declared with
``language: system`` and a bare ``python3 scripts/...`` entry run OUTSIDE the
uv venv. A script (or anything it imports at module level) that resolves only
inside the venv — e.g. ``scripts/docgen.py`` importing ``des`` (src-layout,
venv-installed) — raises ``ModuleNotFoundError`` under the hook interpreter
and rejects every push, with the verdict buried mid-output.

This pin closes the hole CLASS: for EVERY ``language: system`` hook whose
entry invokes ``python3 <script>.py``, execute the script's module-level code
under a bare (non-venv) ``python3`` and assert it imports cleanly. Import-only
(``__name__`` is the module name, not ``__main__``) — the parity contract is
"the hook interpreter can LOAD the script", not "the hook passes", so the
sweep stays fast (<5s total).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"

_IMPORT_TIMEOUT_SECONDS = 30


def _bare_python3() -> str:
    """First ``python3`` on PATH that is NOT inside the running venv.

    Mirrors how git invokes pre-push hooks: the hook entry's bare ``python3``
    resolves against the shell PATH, not the project venv. Candidates under
    ``sys.prefix`` (the venv) are skipped WITHOUT resolving symlinks — a venv
    shim typically symlinks to the system interpreter, and resolving it would
    defeat the venv exclusion.
    """
    venv_prefix = str(Path(sys.prefix))
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_dir) / "python3"
        if not str(candidate).startswith(venv_prefix) and candidate.is_file():
            if os.access(candidate, os.X_OK):
                return str(candidate)
    pytest.skip("no bare python3 outside the venv on PATH")


def _system_python_hook_scripts() -> list[Path]:
    """Every ``*.py`` script invoked via ``python3`` by a ``language: system``
    hook in .pre-commit-config.yaml.

    Entries not invoking ``python3`` (e.g. ``uv run pytest ...``) are out of
    scope — they run inside the venv by construction. Wrapper prefixes
    (``flock ... python3 script.py``) are handled by scanning tokens for the
    ``python3`` word and taking the next token as the script path.
    """
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    scripts: list[Path] = []
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("language") != "system":
                continue
            tokens = shlex.split(hook.get("entry", ""))
            for position, token in enumerate(tokens[:-1]):
                if Path(token).name != "python3":
                    continue
                follower = tokens[position + 1]
                if follower.endswith(".py"):
                    scripts.append(PROJECT_ROOT / follower)
                break
    unique = sorted(set(scripts))
    assert unique, (
        ".pre-commit-config.yaml yielded zero `language: system` python3 hook "
        "scripts — the parser regressed or the config moved; fix the sweep, "
        "do not let the parity pin silently cover nothing"
    )
    return unique


@pytest.mark.parametrize(
    "script",
    _system_python_hook_scripts(),
    ids=lambda script: str(script.relative_to(PROJECT_ROOT)),
)
def test_hook_script_loads_under_bare_python3(script: Path):
    """Module-level code of every system-language python hook script must
    execute under a bare python3 — the interpreter that actually runs it on
    pre-commit/pre-push."""
    assert script.is_file(), (
        f".pre-commit-config.yaml references {script} but it does not exist"
    )
    loader_program = (
        "import importlib.util, sys\n"
        f"path = {str(script)!r}\n"
        "spec = importlib.util.spec_from_file_location('_hook_parity_probe', path)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['_hook_parity_probe'] = module\n"
        "spec.loader.exec_module(module)\n"
    )
    result = subprocess.run(
        [_bare_python3(), "-c", loader_program],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=_IMPORT_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, (
        f"{script.relative_to(PROJECT_ROOT)} cannot be loaded by the bare "
        f"python3 that pre-commit `language: system` hooks actually use "
        f"(exit {result.returncode}). Hooks invoking it will reject every "
        f"push.\nstderr: {result.stderr}"
    )
