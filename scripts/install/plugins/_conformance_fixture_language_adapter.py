"""In-tree conformance fixture for the LanguageAdapterPlugin entry-points group.

F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-02 substrate.

Slice-02 walking-skeleton AT-3 asserts that when ANY plugin is registered in
the ``nwave.lang.adapter`` entry-points group, the loaded class IS-A
:class:`des.ports.language_adapter_plugin.LanguageAdapterPlugin` subclass AND
IS-A :class:`scripts.install.plugins.base.InstallationPlugin` subclass. Slice-02
ships ONLY the substrate (the pure ABC + this conformance fixture); the
first real per-language plugin (Python) lands in slice-05a.

M44 Option (a) refactor (location):

This module lives under ``scripts/install/plugins/`` rather than
``src/des/ports/`` because it cross-imports BOTH the pure ABC at
``des.ports.language_adapter_plugin`` AND the install-pipeline base at
``scripts.install.plugins.base``. The pure ABC in ``src/des/ports/`` MUST NOT
import from ``scripts.*`` (friction #38 build gate + friction #41 F-D-09
architect-side principle). The dual-inheritance is legal here -- ``scripts.*``
modules ship in the dev checkout AND in the installable wheel via the hatch
force-include map (``[tool.hatch.build.targets.wheel.force-include]``).

MRO contract (M44 H2 validated linearization):
``[ConformanceFixtureLanguageAdapter, InstallationPlugin, LanguageAdapterPlugin, ABC, object]``

The fixture is registered in the editable wheel's
``[project.entry-points."nwave.lang.adapter"]`` group under the name
``_conformance_fixture`` -- the underscore prefix signals "in-tree fixture
only, not a real per-language plugin".

The fixture is intentionally inert: every concrete member returns the
narrowest possible value sufficient to satisfy the conformance check.
slice-05a / slice-07 supersede this with real Python and TypeScript
plugins; the fixture remains as the slice-02 floor witness.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from des.ports.language_adapter_plugin import LanguageAdapterPlugin, ProbeResult
from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)


class ConformanceFixtureLanguageAdapter(InstallationPlugin, LanguageAdapterPlugin):
    """The slice-02 conformance fixture -- in-tree witness for AT-3.

    Dual-base concrete plugin (M44 Option a): inherits BOTH
    :class:`InstallationPlugin` (install-pipeline contract: install / verify)
    AND :class:`LanguageAdapterPlugin` (language-adapter contract:
    target_language / port_coverage / register_adapters / probe). MRO:
    ``[ConformanceFixtureLanguageAdapter, InstallationPlugin,
    LanguageAdapterPlugin, ABC, object]`` -- linear, no ambiguity, no
    diamond conflict (the two bases share only ABC + object).

    Registered in the ``nwave.lang.adapter`` entry-points group so the
    discovery substrate has at least one conformant witness without
    depending on slice-05a's real Python plugin.
    """

    def __init__(self) -> None:
        super().__init__(name="_conformance_fixture", priority=1000)

    @property
    def target_language(self) -> str:
        return "_conformance_fixture"

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {}

    def register_adapters(self, registry: Any) -> None:
        """No-op: the fixture wires no real adapters."""

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))

    def install(self, context: InstallContext) -> PluginResult:
        return PluginResult(success=True, plugin_name=self.name, message="fixture")

    def verify(self, context: InstallContext) -> PluginResult:
        return PluginResult(success=True, plugin_name=self.name, message="fixture")
