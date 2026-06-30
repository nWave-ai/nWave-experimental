"""Composition root for gate-layer-test-runner-genericity slice-01 (Mandate-12 SSOT).

Mandate-13 (driving-port-only boundary): the SUT is the stdlib-only STATIC SCAN
over the REAL `src/des/` tree. The scan IS the driving port (Layer-4 static
analysis over the shipped source), exactly like the
`tests/build/.../test_des_bundle_steps.py` stdlib-only static-scan precedent --
it reads each `src/des/**/*.py` as TEXT and `ast.parse`s it; it NEVER imports the
scanned subject, NEVER spawns a subprocess, NEVER touches git. Python + filesystem
only (genericità / target-machine-agnosticism mandate).

WHY AST, not grep (the false-positive the scan must avoid): the net flags actual
`python_for(` CALL nodes, never docstring/comment MENTIONS. `carpaccio_intercept.py`
mentions `python_for(None)` in 8 comments and `_reverify_core.py` in 1 docstring,
but NEITHER calls it -- an `ast.Call` walk excludes them by construction. A
text-grep would false-positive on the prose; the AST walk is precise.

ANTI-VACUITY (the fail-closed contract, mirroring the bundle precedent's
`assert len(py_files) > 0`): if the scan finds ZERO source files (a mis-rooted
SCANNED_ROOT), it RAISES -- it can NEVER silently pass on an empty match. The net
that catches leaks must itself prove it actually scanned something.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_01 import (
    ALLOWLIST,
    RESOLUTION_CALL_NAME,
    SCANNED_ROOT,
    InterpreterLeak,
    SourceFile,
)


class ScanRootEmpty(RuntimeError):
    """Raised when the scan root holds zero `.py` files -- fail-closed anti-vacuity.

    A scan that matched nothing because it scanned NOTHING is the silent-pass
    failure mode this net exists to prevent. We raise rather than return an empty
    leak list so an empty match can never be mistaken for "no leaks".
    """


@dataclass
class GateLayerScan:
    """The static-scan driving port over nWave's own gate/wave source tree.

    One method drives the REAL scan over `src/des/`; the AT observes ONLY the
    structured `InterpreterLeak` list it returns (no production gate symbol is
    imported -- the scan reads source as text).
    """

    scanned_root: Path = SCANNED_ROOT
    scanned_file_count: int = field(default=0)

    # --- the driving port: scan the REAL src/des/ tree for leaks -------------

    def find_interpreter_leaks(self) -> list[InterpreterLeak]:
        """Scan every `src/des/**/*.py` and return interpreter-resolution leaks.

        A leak = an `ast.Call` to `python_for(...)` located in a file OUTSIDE the
        allowlist. The allowlisted two boundaries (interpreter.py, pytest_runner.py)
        are legitimate and excluded.

        Fail-closed (anti-vacuity): raise `ScanRootEmpty` if zero `.py` files are
        found -- the scan must prove it actually scanned the tree before any
        emptiness can be read as "clean".
        """
        py_files = self._source_files()
        if not py_files:
            raise ScanRootEmpty(
                f"gate-layer scan found ZERO python files under {self.scanned_root} "
                "-- mis-rooted scan, refusing to report a vacuous clean result"
            )
        self.scanned_file_count = len(py_files)

        leaks: list[InterpreterLeak] = []
        for src in py_files:
            if self._repo_relative_posix(src) in ALLOWLIST:
                continue  # sanctioned boundary -- python here is correct
            leaks.extend(self._leaks_in_file(src))
        # Deterministic order so the failure message (and any consumer) is stable.
        leaks.sort(key=lambda leak: (str(leak.file), leak.line))
        return leaks

    # --- internals -----------------------------------------------------------

    def _source_files(self) -> list[SourceFile]:
        """Every `.py` under the scanned root (sorted, stable)."""
        return [
            SourceFile(p)
            for p in sorted(self.scanned_root.rglob("*.py"))
            if p.is_file()
        ]

    def _repo_relative_posix(self, src: Path) -> str:
        """`src/des/...`-style POSIX path for allowlist membership (cross-OS)."""
        repo_root = self.scanned_root.parent.parent  # src/des -> repo root
        return src.relative_to(repo_root).as_posix()

    def _leaks_in_file(self, src: SourceFile) -> list[InterpreterLeak]:
        """Every `python_for(...)` CALL node in one source file (AST, not grep)."""
        text = Path(src).read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(src))
        lines = text.splitlines()
        found: list[InterpreterLeak] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if self._callee_name(node.func) != RESOLUTION_CALL_NAME:
                continue
            lineno = getattr(node, "lineno", 0)
            snippet = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            found.append(InterpreterLeak(file=Path(src), line=lineno, snippet=snippet))
        return found

    @staticmethod
    def _callee_name(func: ast.expr) -> str | None:
        """Resolve the called name: `python_for(...)` or `mod.python_for(...)`."""
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None
