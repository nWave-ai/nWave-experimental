"""The ``nwave-lang-typescript`` LanguageAdapterPlugin -- the TS reference plugin.

unified-language-adapter-registry slice-03 (DESIGN slice-07, component C12).
ONE ``register_adapters(registry)`` call wires all 3 ``LanguageAdapterRegistry``
slots (contract-gate, environmental-e2e, robustness-density -- C13) under the
resolved tool-name ``"vitest"`` (DDD-U5), mirroring ``NwaveLangPython`` (and
``NwaveLangRust``) exactly: dual-base concrete plugin (``InstallationPlugin``
+ ``LanguageAdapterPlugin``), purely additive -- ZERO edit to the slice-01
seam or to any slice-02 file (the language-neutrality proof).

Lives under ``scripts/install/plugins/`` (NOT ``src/des/**``) so the dual
inheritance is legal -- ``src/des/**`` MUST NOT import ``scripts.*`` (F-D-09).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from des.adapters.driven.contract_gate.vitest_contract_gate_adapter import (
    VitestContractGateAdapter,
)
from des.adapters.driven.e2e.typescript_environmental_e2e_adapter import (
    TypeScriptEnvironmentalE2EAdapter,
)
from des.adapters.driven.robustness.typescript_robustness_density_adapter import (
    TypeScriptRobustnessDensityAdapter,
)
from des.ports.language_adapter_plugin import LanguageAdapterPlugin, ProbeResult
from scripts.install.plugins.base import InstallationPlugin, PluginResult


if TYPE_CHECKING:
    from scripts.install.plugins.base import InstallContext


# The tool-name ``resolve_runner``/``GLOBAL_REGISTRY.lookup*`` key on for a
# TypeScript target (test_runner_port.py's vitest registry row) -- the plugin
# registers its 3 new facets under THIS token (DDD-U5), never `target_language`.
_VITEST_TOKEN = "vitest"

_CONTRACT_GATE_PORT = "run_contract_gate"
_ENVIRONMENTAL_E2E_PORT = "verify_environmental_e2e"
_ROBUSTNESS_DENSITY_PORT = "check_robustness_density"


class NwaveLangTypescript(InstallationPlugin, LanguageAdapterPlugin):
    """The TypeScript per-language plugin -- wires all 3 new unified-registry slots.

    Dual-base (mirrors ``NwaveLangPython``): inherits BOTH ``InstallationPlugin``
    AND ``LanguageAdapterPlugin``.
    """

    def __init__(self) -> None:
        super().__init__(name="nwave-lang-typescript", priority=1000)

    @property
    def target_language(self) -> str:
        return "typescript"

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            _CONTRACT_GATE_PORT: True,
            _ENVIRONMENTAL_E2E_PORT: True,
            _ROBUSTNESS_DENSITY_PORT: True,
        }

    def register_adapters(self, registry: Any) -> None:
        """Wire all 3 new slots into ``registry`` under the ``"vitest"`` token.

        ONE call wires the contract-gate (C13), environmental-e2e (C13), and
        robustness-density (C13) facets -- the slice-03 unification pin.
        """
        registry.register_contract_gate(_VITEST_TOKEN, VitestContractGateAdapter())
        registry.register_environmental_e2e(
            _VITEST_TOKEN, TypeScriptEnvironmentalE2EAdapter()
        )
        registry.register_robustness_density(
            _VITEST_TOKEN, TypeScriptRobustnessDensityAdapter()
        )

    def probe(self) -> ProbeResult:
        """Earned-Trust probe: no slice-03 AT exercises this method."""
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))

    def install(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True, plugin_name=self.name, message="nwave-lang-typescript"
        )

    def verify(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True, plugin_name=self.name, message="nwave-lang-typescript"
        )
