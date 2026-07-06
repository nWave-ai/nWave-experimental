"""The ``nwave-lang-python`` LanguageAdapterPlugin -- the Python reference plugin.

unified-language-adapter-registry slice-02 (DESIGN slice-05a, component C11).
ONE ``register_adapters(registry)`` call wires all 3 NEW
``LanguageAdapterRegistry`` slots (contract-gate, environmental-e2e,
robustness-density -- C8/C9/C10) under the resolved tool-name ``"pytest"``
(DDD-U5), mirroring the shipped ``NwaveLangRust`` shape exactly (dual-base
concrete plugin: ``InstallationPlugin`` + ``LanguageAdapterPlugin``).

Lives under ``scripts/install/plugins/`` (NOT ``src/des/**``) so the dual
inheritance is legal -- ``src/des/**`` MUST NOT import ``scripts.*`` (F-D-09).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from des.adapters.driven.contract_gate.pytest_contract_gate_adapter import (
    PythonContractGateAdapter,
)
from des.adapters.driven.e2e.python_environmental_e2e_adapter import (
    PythonEnvironmentalE2EAdapter,
)
from des.adapters.driven.robustness.python_robustness_density_adapter import (
    PythonRobustnessDensityAdapter,
)
from des.ports.language_adapter_plugin import LanguageAdapterPlugin, ProbeResult
from scripts.install.plugins.base import InstallationPlugin, PluginResult


if TYPE_CHECKING:
    from scripts.install.plugins.base import InstallContext


# The tool-name ``resolve_runner``/``GLOBAL_REGISTRY.lookup*`` key on for a
# Python target (test_runner_port.py's pytest registry row) -- the plugin
# registers its 3 new facets under THIS token (DDD-U5), never `target_language`.
_PYTEST_TOKEN = "pytest"

_CONTRACT_GATE_PORT = "run_contract_gate"
_ENVIRONMENTAL_E2E_PORT = "verify_environmental_e2e"
_ROBUSTNESS_DENSITY_PORT = "check_robustness_density"


class NwaveLangPython(InstallationPlugin, LanguageAdapterPlugin):
    """The Python per-language plugin -- wires all 3 new unified-registry slots.

    Dual-base (mirrors ``NwaveLangRust``): inherits BOTH ``InstallationPlugin``
    AND ``LanguageAdapterPlugin``.
    """

    def __init__(self) -> None:
        super().__init__(name="nwave-lang-python", priority=1000)

    @property
    def target_language(self) -> str:
        return "python"

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            _CONTRACT_GATE_PORT: True,
            _ENVIRONMENTAL_E2E_PORT: True,
            _ROBUSTNESS_DENSITY_PORT: True,
        }

    def register_adapters(self, registry: Any) -> None:
        """Wire all 3 new slots into ``registry`` under the ``"pytest"`` token.

        ONE call wires the contract-gate (C8), environmental-e2e (C9), and
        robustness-density (C10) facets -- the slice-02 unification pin.
        """
        registry.register_contract_gate(_PYTEST_TOKEN, PythonContractGateAdapter())
        registry.register_environmental_e2e(
            _PYTEST_TOKEN, PythonEnvironmentalE2EAdapter()
        )
        registry.register_robustness_density(
            _PYTEST_TOKEN, PythonRobustnessDensityAdapter()
        )

    def probe(self) -> ProbeResult:
        """Earned-Trust probe: the running interpreter IS the Python toolchain."""
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))

    def install(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True, plugin_name=self.name, message="nwave-lang-python"
        )

    def verify(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True, plugin_name=self.name, message="nwave-lang-python"
        )
