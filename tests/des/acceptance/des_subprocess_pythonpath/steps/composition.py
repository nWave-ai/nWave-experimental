"""Composition root for fix-des-subprocess-pythonpath slice-01 (Mandate-12 + 13).

The single source of truth for the business logic the step methods invoke. Step
bodies delegate here -- no inline logic in the .feature bindings.

Mandate-13 (Driving-Port-Only Boundary): the SUT is driven through the REAL
surfaces only --
  * AC-1 drives the REAL AST arch-walk over the REAL ``src/des/**`` tree;
  * AC-2 drives the REAL ``des.runtime.interpreter.des_spawn`` to spawn a REAL
    hermetic ``python -m des.cli.<readonly> --help`` subprocess under a
    des-stripped env;
  * AC-3/AC-4 drive the REAL ``des_spawn`` with ``subprocess.run`` spied.

IMPORT-GUARD CONTRACT (atdd_pure RED-not-BROKEN): ``des_spawn`` does NOT exist at
HEAD. The composition imports it LAZILY inside each method, never at module top
level, so collection NEVER errors. When ``des_spawn`` is absent the helper-driving
methods raise ``AssertionError`` (RED, impl missing) -- not ``ImportError``
(BROKEN). The arch-walk (AC-1) needs no helper and fails on a real non-empty
violation list at HEAD.

HERMETICITY (tests/meta/test_acceptance_hermeticity.py): the AC-2 subprocess is
hermetic -- ``python -m des.cli.*`` only; this file reaches no real developer
home directory and stages no personal-hook paths.
"""

from __future__ import annotations

import ast
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from .domain_types import (
    ArchBanViolation,
    ChildImportOutcome,
    SanctionedDesModuleSubcommand,
    SpawnCapability,
    SpiedSpawnCall,
)


# --------------------------------------------------------------------------
# Repo geometry -- the REAL src/des tree the AC-1 arch-walk scans.
# --------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DES_ROOT = _PROJECT_ROOT / "src" / "des"
# The sanctioned helper home -- the ONE file allowed to spawn a des-module
# interpreter inline (it IS the helper boundary).
_SANCTIONED_HELPER = _DES_ROOT / "runtime" / "interpreter.py"

_SCAFFOLD_MARKER = "fix-des-subprocess-pythonpath RED scaffold"

# A real, read-only des.cli subcommand (verified: `des.cli.roadmap --help`
# exits 0, prints usage, mutates nothing).
SANCTIONED_SUBCOMMAND = SanctionedDesModuleSubcommand(
    module="des.cli.roadmap", readonly_arg="--help"
)


def _is_python_for_call(node: ast.expr) -> bool:
    """True iff ``node`` is a ``python_for(...)`` call (argv[0] of a sanctioned
    interpreter spawn done INLINE)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "python_for"
    )


_SUBPROCESS_SPAWNERS = {"run", "Popen", "call", "check_call", "check_output"}


def _subprocess_argv_elements(call: ast.Call) -> list[ast.expr] | None:
    """If ``call`` is a ``subprocess.*`` spawner with a non-empty list/tuple first
    arg, return that sequence's element list; else None."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in _SUBPROCESS_SPAWNERS):
        return None
    if not (isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
        return None
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
        return list(first.elts)
    return None


def _spawns_des_module(argv: list[ast.expr]) -> bool:
    """True iff ``argv`` is a ``-m <module>`` spawn whose module literal starts
    with ``des.`` -- i.e. a des-module spawn (the AC-1 threat). A ``-m pytest``
    (or any non-``des.`` module) spawn is NOT a des-module spawn and is exempt
    per the feature-delta [REF] Out-of-Scope (pytest spawns are a different shape
    and cannot lose ``des`` from a des-module child path)."""
    for i, elem in enumerate(argv[:-1]):
        if (
            isinstance(elem, ast.Constant)
            and elem.value == "-m"
            and isinstance(module := argv[i + 1], ast.Constant)
            and isinstance(module.value, str)
            and module.value.startswith("des.")
        ):
            return True
    return False


class SubprocessPythonpathComposition:
    """Drives the real des_spawn helper + the real arch-walk (the SUT surfaces)."""

    # ------------------------------------------------------------------
    # AC-1 -- arch-ban over the REAL src/des/** tree (no helper needed).
    # ------------------------------------------------------------------
    def des_modules(self) -> list[Path]:
        """Every ``src/des/**/*.py`` except the sanctioned helper home."""
        modules = sorted(_DES_ROOT.rglob("*.py"))
        return [m for m in modules if m != _SANCTIONED_HELPER]

    def inline_python_for_spawn_violations(self) -> list[ArchBanViolation]:
        """Collect every INLINE des-module interpreter spawn outside ``des_spawn``.

        A violation = a ``subprocess.*`` spawner in a ``src/des/**`` module
        (other than ``interpreter.py``) whose argv[0] is a ``python_for(...)``
        call AND whose ``-m <module>`` is a ``des`` module (a literal starting
        ``des.``) -- i.e. a sanctioned-interpreter des-module spawn done inline
        rather than routed through the centralized ``des_spawn`` helper. A
        ``-m pytest`` / non-``des.`` module spawn is OUT OF SCOPE (different
        shape; cannot lose ``des`` from a des-module child path). GREEN is an
        EMPTY list.
        """
        violations: list[ArchBanViolation] = []
        for path in self.des_modules():
            rel = path.relative_to(_PROJECT_ROOT)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                argv = _subprocess_argv_elements(node)
                if argv is None or not _is_python_for_call(argv[0]):
                    continue
                if not _spawns_des_module(argv):
                    continue
                violations.append(
                    ArchBanViolation(
                        location=f"{rel}:{node.lineno}",
                        detail=(
                            "inline subprocess spawn of a des module with "
                            "argv[0]=python_for(...) -- route through des_spawn(...)"
                        ),
                    )
                )
        return violations

    # ------------------------------------------------------------------
    # AC-2 -- importable child via the REAL des_spawn under a des-stripped env.
    # ------------------------------------------------------------------
    def spawn_child_under_des_stripped_env(
        self, subcommand: SanctionedDesModuleSubcommand
    ) -> ChildImportOutcome:
        """Drive the REAL ``des_spawn`` to spawn ``python -m <subcommand> --help``
        under an env where ``des`` is stripped from ``sys.path`` / ``PYTHONPATH``.

        The child can only exit 0 if ``des_spawn`` injected the des root via
        ``des_subprocess_env`` (otherwise ``ModuleNotFoundError: des``).

        RED at HEAD: ``des_spawn`` is absent -> AssertionError (impl missing),
        NOT ImportError.
        """
        des_spawn = self._load_des_spawn_or_red()

        # A des-stripped base env: PYTHONPATH cleared (the child must NOT inherit
        # any des root from the parent's env). des_spawn must re-inject it.
        stripped_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        stripped_env["PYTHONPATH"] = ""

        completed = des_spawn(
            None,
            subcommand.module,
            subcommand.readonly_arg,
            env=stripped_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode == 0:
            return ChildImportOutcome.IMPORTED
        return ChildImportOutcome.MODULE_NOT_FOUND

    # ------------------------------------------------------------------
    # AC-3 / AC-4 -- by-construction env + kwargs forwarding via spied run.
    # ------------------------------------------------------------------
    def spawn_with_spied_run(
        self,
        capability: SpawnCapability,
        *module_args: str,
        caller_kwargs: dict[str, object] | None = None,
    ) -> SpiedSpawnCall:
        """Drive the REAL ``des_spawn`` with ``subprocess.run`` monkeypatched,
        capturing the exact argv / env / kwargs the helper composed.

        Used by AC-3 (argv[0]==python_for(capability), env has des root -- WITHOUT
        the caller passing either) and AC-4 (caller kwargs forwarded; a
        caller-supplied env merged through des_subprocess_env(base=...), not
        dropped).

        RED at HEAD: ``des_spawn`` is absent -> AssertionError (impl missing).
        """
        des_spawn = self._load_des_spawn_or_red()
        interpreter = self._load_interpreter_module()

        spied = SpiedSpawnCall()

        def _spy(argv, *args, **kwargs):  # type: ignore[no-untyped-def]
            spied.argv = list(argv)
            spied.env = dict(kwargs.get("env") or {})
            spied.kwargs = {k: v for k, v in kwargs.items() if k != "env"}
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        cap = None if capability is SpawnCapability.NONE else capability.value
        kw = dict(caller_kwargs or {})

        original = interpreter.subprocess.run
        try:
            interpreter.subprocess.run = _spy  # type: ignore[assignment]
            des_spawn(cap, *module_args, **kw)
        finally:
            interpreter.subprocess.run = original  # type: ignore[assignment]

        return spied

    def expected_interpreter_for(self, capability: SpawnCapability) -> str:
        """The interpreter ``python_for(capability)`` resolves to (AC-3 oracle:
        a SHIPPED-artifact reference, not a value the test fabricated)."""
        interpreter = self._load_interpreter_module()
        cap = None if capability is SpawnCapability.NONE else capability.value
        return interpreter.python_for(cap)

    def expected_des_root_on_pythonpath(self) -> str:
        """The des root ``des_subprocess_env`` guarantees on PYTHONPATH (AC-3
        oracle: read from the REAL helper, not fabricated)."""
        interpreter = self._load_interpreter_module()
        env = interpreter.des_subprocess_env()
        return env["PYTHONPATH"].split(os.pathsep)[0]

    # ------------------------------------------------------------------
    # Import-guard helpers -- LAZY, RED-not-BROKEN.
    # ------------------------------------------------------------------
    def _load_interpreter_module(self):  # type: ignore[no-untyped-def]
        from des.runtime import interpreter

        return interpreter

    def _load_des_spawn_or_red(self) -> Callable[..., subprocess.CompletedProcess]:
        """Return the real ``des_spawn`` or raise AssertionError (RED) if absent.

        atdd_pure: the helper is the not-yet-implemented production seam. Its
        absence MUST surface as a semantic AssertionError (impl missing), never
        an ImportError (BROKEN) that the pre-DELIVER gate would reject.
        """
        interpreter = self._load_interpreter_module()
        des_spawn = getattr(interpreter, "des_spawn", None)
        assert des_spawn is not None and callable(des_spawn), (
            f"{_SCAFFOLD_MARKER}: des.runtime.interpreter.des_spawn does not exist "
            "yet -- DELIVER must add the centralized helper composing "
            "python_for(capability) + des_subprocess_env(base=caller_env)"
        )
        return des_spawn
