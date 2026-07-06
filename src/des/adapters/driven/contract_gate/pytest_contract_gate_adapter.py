"""PythonContractGateAdapter -- the Python reference ContractGatePort facet (C8).

unified-language-adapter-registry slice-02 (DESIGN slice-05a, component C8).
Registered by ``nwave_lang_python`` under the resolved tool-name ``"pytest"``
(DDD-U5, ``LanguageAdapterRegistry.register_contract_gate``).

Runs the TARGET codebase's own pytest suite directly, with no marker filter:
a customer Python repo has no reason to carry nWave-dev's own ``unit or
integration or acceptance`` dogfood marker convention (that scope is the
nwave-dev-specific fallback body -- ``run_contract_gate.py::_run_contract_suite``
-- the seam falls through to when no adapter is registered, unchanged and
untouched by this adapter).

The interpreter is resolved through ``python_for(None)`` (the F-21 boundary
contract: no raw ``sys.executable`` in ``src/des/**``). ``None`` -- not
``"pytest"`` -- is deliberate: this adapter is reached from WITHIN the gate's
own already-running, pytest-capable interpreter (the dogfood / subprocess-e2e
driving process), whose env (including the caller's ``PYTHONPATH``) the spawned
pytest child inherits by default (``F-DES-SUBPROCESS-PYTHONPATH-PROPAGATION``).
``python_for("pytest")`` would re-probe/re-climb the interpreter ladder and can
resolve a DIFFERENT rung interpreter that does not carry the caller's
``PYTHONPATH`` -- the running interpreter is already the right one, so ``None``
returns it unconditionally without a redundant probe.

Stdlib ``subprocess`` + the resolved interpreter, per F-D-09 (no ``scripts.*``
import from ``src/des/**``).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.contract_gate_port import ContractVerdict
from des.runtime.interpreter import python_for


if TYPE_CHECKING:
    from pathlib import Path


_PYTEST_RUNNER = "pytest"


class PythonContractGateAdapter:
    """Runs the target Python codebase's own pytest suite; reports the verdict."""

    def collect_scope(self, repo: Path) -> list[str]:
        """Enumerate the target's pytest node-id scope (``--collect-only``)."""
        completed = subprocess.run(
            [python_for(None), "-m", "pytest", "--collect-only", "-q"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        return [line for line in completed.stdout.splitlines() if "::" in line]

    def run_suite(self, repo: Path) -> ContractVerdict:
        """Run the target's whole pytest suite; return the observable verdict."""
        completed = subprocess.run(
            [python_for(None), "-m", "pytest", "-p", "no:cacheprovider"],
            cwd=repo,
            check=False,
        )
        return ContractVerdict(passed=completed.returncode == 0, runner=_PYTEST_RUNNER)


__all__ = ["PythonContractGateAdapter"]
