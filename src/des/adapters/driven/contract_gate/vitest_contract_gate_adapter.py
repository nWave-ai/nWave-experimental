"""VitestContractGateAdapter -- the TypeScript ContractGatePort facet (C13).

unified-language-adapter-registry slice-03 (DESIGN slice-07, component C13).
Registered by ``nwave_lang_typescript`` under the resolved tool-name
``"vitest"`` (DDD-U5, ``LanguageAdapterRegistry.register_contract_gate``).
Mirrors ``PythonContractGateAdapter`` (C8) EXACTLY, generalized only by
tool-name pytest -> vitest: runs the TARGET codebase's own vitest suite
directly, with no marker filter -- a customer TypeScript repo has no reason
to carry nWave-dev's own dogfood marker convention.

The vitest binary is resolved through the SAME shared 3-rung discovery scale
(``des.adapters.driven.runner.tool_discovery.resolve_tool``) the shipped
``run_vitest_scope`` run-facet already uses -- deliberately NOT ``python_for``,
which resolves Python interpreters only and does not apply to a Node binary.
An unresolvable vitest raises ``RunnerAdapterUnavailable`` naming the
remediation (the LOUD INDETERMINATE channel, mirroring ``run_vitest_scope``),
never a silent pass.

Stdlib ``subprocess`` + the shared ``resolve_tool`` scale, per F-D-09 (no
``scripts.*`` import from ``src/des/**``) and F-21 (no raw ``sys.executable``
in ``src/des/**`` -- this adapter shells a NODE binary, not a Python
interpreter, so ``python_for`` does not apply here).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.adapters.driven.runner.vitest_runner import VITEST_KNOWN_LOCATIONS
from des.ports.driven_ports.contract_gate_port import ContractVerdict
from des.ports.test_runner_port import RunnerAdapterUnavailable


if TYPE_CHECKING:
    from pathlib import Path


_VITEST_RUNNER = "vitest"


class VitestContractGateAdapter:
    """Runs the target TypeScript codebase's own vitest suite; reports the verdict."""

    def collect_scope(self, repo: Path) -> list[str]:
        """Enumerate the target's vitest test-file scope (file-granularity)."""
        return [str(path) for path in sorted(repo.rglob("*.test.ts"))]

    def run_suite(self, repo: Path) -> ContractVerdict:
        """Run the target's whole vitest suite; return the observable verdict."""
        resolution = resolve_tool(_VITEST_RUNNER, VITEST_KNOWN_LOCATIONS)
        if resolution.path is None:
            raise RunnerAdapterUnavailable(
                _VITEST_RUNNER, reason=resolution.remediation
            )
        completed = subprocess.run(
            [resolution.path, "run"],
            cwd=repo,
            check=False,
        )
        return ContractVerdict(passed=completed.returncode == 0, runner=_VITEST_RUNNER)


__all__ = ["VitestContractGateAdapter"]
