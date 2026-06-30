"""The ``nwave-lang-rust`` LanguageAdapterPlugin -- the cargo unification carrier.

ADR-RTR-001 C3 / D2. Ale directive 2026-06-20 #2: the test-runner lives UNDER the
unified ``LanguageAdapterPlugin``, NOT as a standalone thing. This plugin is that
carrier for Rust: its ``register_adapters(registry)`` writes the cargo run-facet
(``run_cargo_scope``, C1) into the runner registry (C2) under the EXISTING
``"cargo-test"`` token (D8 -- no rename), so ``TestRunnerPort.resolve`` ->
registry-key -> plugin-registration agree by construction. JS/TS/Go/Java slot in
identically later (each plugin registers its own run-facet).

Dual-base concrete plugin, MIRRORING the conformance fixture's legal MRO
(``_conformance_fixture_language_adapter.py``):
``[NwaveLangRust, InstallationPlugin, LanguageAdapterPlugin, ABC, object]``. Lives
under ``scripts/install/plugins/`` (NOT ``src/des/**``) so the dual inheritance is
legal -- ``src/des/**`` MUST NOT import ``scripts.*`` (F-D-09 / friction #38/#41);
the concrete plugin site CAN cross-import des.* ports + adapters. Registered in
the ``nwave.lang.adapter`` entry-points group (pyproject.toml) so
``seed_runner_registry()`` (D6) discovers it on an installed target.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from des.adapters.driven.runner.cargo_runner import (
    CARGO_KNOWN_LOCATIONS,
    run_cargo_scope,
)
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.ports.language_adapter_plugin import LanguageAdapterPlugin, ProbeResult
from scripts.install.plugins.base import (
    InstallationPlugin,
    PluginResult,
)


if TYPE_CHECKING:
    from scripts.install.plugins.base import InstallContext


# The EXISTING runner token TestRunnerPort.resolve returns for a Cargo.toml target
# (test_runner_port.py:134). The plugin registers the cargo run-facet under THIS
# token (D8 -- no rename) so resolve -> registry-key agree by construction.
_CARGO_TOKEN = "cargo-test"

# The port-id this Rust plugin covers; every other language-adapter port is a GAP
# (the doctor CLI surfaces them) -- this feature ships ONLY the test-runner facet.
_TEST_RUNNER_PORT = "test-runner"


class NwaveLangRust(InstallationPlugin, LanguageAdapterPlugin):
    """The Rust per-language plugin -- registers the cargo run-facet (unification).

    Dual-base (M44 Option a, mirroring the conformance fixture): inherits BOTH
    ``InstallationPlugin`` (install-pipeline contract) AND ``LanguageAdapterPlugin``
    (language-adapter contract). MRO is linear -- the two bases share only
    ``ABC`` + ``object``.
    """

    def __init__(self) -> None:
        super().__init__(name="nwave-lang-rust", priority=1000)

    @property
    def target_language(self) -> str:
        return "rust"

    @property
    def port_coverage(self) -> dict[str, bool]:
        # ONLY the test-runner facet is shipped for Rust in this feature; every
        # other language-adapter port is a GAP the doctor CLI reports.
        return {_TEST_RUNNER_PORT: True}

    def register_adapters(self, registry: Any) -> None:
        """Wire the cargo run-facet into the registry under the cargo-test token.

        THE unification (D2/D8): the runner registers THROUGH this plugin under
        the EXISTING ``"cargo-test"`` token, NOT via a hardcoded ``if name == ...``
        branch. ``registry.lookup("cargo-test")`` resolves to ``run_cargo_scope``.
        """
        registry.register(_CARGO_TOKEN, run_cargo_scope)

    def probe(self) -> ProbeResult:
        """Earned-Trust probe: resolve cargo via the SHARED discovery scale.

        Shares the ``resolve_tool`` scale with the runner (so probe-says-present
        implies run-can-find), exercising the WSL2 PATH lie: a cargo present only
        in ``~/.cargo/bin`` (off PATH) resolves via the known-location rung ->
        ``ok=True``. cargo unresolvable -> ``ok=False`` with the test-runner port
        named in ``missing_ports``.
        """
        resolution = resolve_tool("cargo", CARGO_KNOWN_LOCATIONS)
        resolved = resolution.path is not None
        return ProbeResult(
            ok=resolved,
            missing_ports=[] if resolved else [_TEST_RUNNER_PORT],
            probed_at=datetime.now(UTC),
        )

    def install(self, context: InstallContext) -> PluginResult:
        # The plugin ships no install-time artefacts of its own; it is the
        # entry-points carrier the runner registry seeds at gate time.
        return PluginResult(
            success=True, plugin_name=self.name, message="nwave-lang-rust"
        )

    def verify(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True, plugin_name=self.name, message="nwave-lang-rust"
        )
