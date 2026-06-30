"""Composition root for the whole-tree resolution arch-net (D7, Mandate-12 SSOT).

Mandate-13 (driving-port-only boundary): the SUT is the stdlib-only STATIC SCAN
over the REAL ``src/des/cli/run_contract_gate.py``. The scan IS the driving port
(Layer-4 static analysis over the shipped source) -- it reads the module as TEXT
and ``ast.parse``s it; it NEVER imports the scanned subject, NEVER spawns a
subprocess, NEVER touches git. Python + filesystem only (genericità).

The invariant: in EACH whole-tree mode function the FIRST call into a pytest-bound
leg must be PRECEDED (by source line) by a call to a whole-tree runner resolver --
EITHER the RUN router or the DIGEST router (``WHOLE_TREE_RESOLVERS``). A mode
reaching a pytest leg with no preceding resolver call is an ``UnroutedMode``.

ANTI-VACUITY (fail-closed): if the scan locates none of the four whole-tree mode
functions (a mis-pointed source), it RAISES -- it can NEVER silently return an
empty leak list that reads as "all modes routed".
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .domain_types_whole_tree import (
    PYTEST_BOUND_LEGS,
    WHOLE_TREE_GATE_SOURCE,
    WHOLE_TREE_MODES,
    WHOLE_TREE_RESOLVERS,
    UnroutedMode,
)


class ScanSubjectMissing(RuntimeError):
    """Raised when the scan finds none of the whole-tree mode functions.

    A scan that reported "all routed" because it scanned NOTHING is the silent-pass
    failure mode this net exists to prevent. We raise rather than return an empty
    leak list so an empty match can never be mistaken for "no unrouted modes".
    """


@dataclass
class WholeTreeResolutionScan:
    """The static-scan driving port over the whole-tree contract-gate module."""

    source: Path = WHOLE_TREE_GATE_SOURCE

    # --- the driving port: scan each whole-tree mode for the ordering --------

    def find_unrouted_modes(self) -> list[UnroutedMode]:
        """Every whole-tree mode that reaches a pytest leg with no preceding resolver.

        Fail-closed (anti-vacuity): raise ``ScanSubjectMissing`` if NONE of the
        four whole-tree mode functions are found -- the scan must prove it actually
        located the modes before any emptiness can be read as "all routed".
        """
        funcs = self._mode_functions()
        if not funcs:
            raise ScanSubjectMissing(
                f"whole-tree resolution scan located NONE of {sorted(WHOLE_TREE_MODES)} "
                f"in {self.source} -- mis-pointed scan, refusing a vacuous clean result"
            )
        unrouted: list[UnroutedMode] = []
        for name, fn in sorted(funcs.items()):
            leak = self._unrouted(name, fn)
            if leak is not None:
                unrouted.append(leak)
        unrouted.sort(key=lambda m: (m.mode, m.leg_line))
        return unrouted

    # --- internals -----------------------------------------------------------

    def _mode_functions(self) -> dict[str, ast.FunctionDef]:
        """The AST FunctionDef of each whole-tree mode present in the source."""
        if not self.source.is_file():
            return {}
        tree = ast.parse(
            self.source.read_text(encoding="utf-8"), filename=str(self.source)
        )
        found: dict[str, ast.FunctionDef] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in WHOLE_TREE_MODES:
                found[node.name] = node
        return found

    def _unrouted(self, name: str, fn: ast.FunctionDef) -> UnroutedMode | None:
        """The leak for one mode, or None when it resolves before any pytest leg."""
        resolver_line = self._first_call_line(fn, set(WHOLE_TREE_RESOLVERS))
        leg_line, leg = self._first_call(fn, PYTEST_BOUND_LEGS)
        if leg_line is None or leg is None:
            return None  # mode reaches no pytest leg -> nothing to route
        if resolver_line is not None and resolver_line < leg_line:
            return None  # resolved before the pytest leg -> correctly routed
        return UnroutedMode(
            mode=name, leg=leg, leg_line=leg_line, resolver_line=resolver_line
        )

    @staticmethod
    def _first_call_line(fn: ast.FunctionDef, names: set[str]) -> int | None:
        line, _ = WholeTreeResolutionScan._first_call(fn, names)
        return line

    @staticmethod
    def _first_call(
        fn: ast.FunctionDef, names: set[str]
    ) -> tuple[int | None, str | None]:
        """The (lineno, name) of the earliest call to any ``names`` callee in ``fn``."""
        best_line: int | None = None
        best_name: str | None = None
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            callee = WholeTreeResolutionScan._callee_name(node.func)
            if callee not in names:
                continue
            lineno = getattr(node, "lineno", 0)
            if best_line is None or lineno < best_line:
                best_line, best_name = lineno, callee
        return best_line, best_name

    @staticmethod
    def _callee_name(func: ast.expr) -> str | None:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None
