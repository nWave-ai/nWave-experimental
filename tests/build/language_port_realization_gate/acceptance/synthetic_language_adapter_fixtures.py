"""Synthetic ``LanguageAdapterPlugin`` fixtures for language-port-realization-gate ATs.

Test-brittleness fix (#92): the ATs in this feature originally drove the REAL
shipped ``NwaveLangPython`` / ``NwaveLangTypescript`` plugins directly,
pinning the "registered-but-lying" smoking gun (``port_coverage`` declares 3
ports ``True`` while ``verify_environmental_e2e`` / ``check_robustness_density``
are pure ``raise NotImplementedError`` stubs) to nWave-dev's OWN, mutable
adapter implementation state. Once ``implement-language-adapter-facets``
genuinely implemented those facets, every AT asserting "the shipped plugin is
flagged as a liar" broke -- not because the gate regressed, but because the
premise the fixture encoded (stub-backed) silently became false out from
under the test.

This module reproduces the EXACT smoking-gun SHAPE as a CONTROLLED,
self-contained fixture: a plugin that declares all 3 ports ``True``, backs
``run_contract_gate`` with a genuinely-implemented (non-stub) facet, and
backs ``verify_environmental_e2e`` / ``check_robustness_density`` with pure
``raise NotImplementedError`` stubs. Every AT in this feature that needs a
"registered-but-lying" plugin should construct one of the two concrete
zero-arg subclasses below instead of importing a real shipped plugin --  the
outcome is then STABLE regardless of whether nWave-dev's own Python/
TypeScript facets are stubs or genuinely implemented.

Two concrete, zero-arg subclasses (``...CSharp`` / ``...Kotlin``, echoing the
feature-delta's own founder narrative -- "I add csharp to the toml and the
failures tell me what to implement") exist so:

  * in-process discovery tests can construct instances directly
    (``SyntheticLiarLanguageAdapterPluginCSharp()``), and
  * subprocess/CLI tests can resolve them via ``importlib.metadata.EntryPoint
    .load()()`` (a zero-arg call) through the repeatable ``--plugin
    <module>:<Class>`` flag or an injected raw ``EntryPoint``.

Both subclasses live in THIS file, so the gate's FAIL-LOUD diagnostic
(``file:line`` of the stub method) always names a real, stable, repo-relative
path -- this module -- never a production adapter file whose stub-vs-real
status can change out from under the test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from des.ports.language_adapter_plugin import LanguageAdapterPlugin, ProbeResult


if TYPE_CHECKING:
    from pathlib import Path


RUN_CONTRACT_GATE = "run_contract_gate"
VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"

_FIXTURE_TOOL_TOKEN = "synthetic-liar-fixture-tool"


class RealFixtureContractGateAdapter:
    """A genuinely-implemented ``ContractGatePort`` facet -- NOT a stub."""

    def collect_scope(self, repo: Path) -> list[str]:
        return ["fixture-scope-item"]

    def run_suite(self, repo: Path) -> dict[str, object]:
        return {"verdict": "PASS"}


class StubFixtureEnvironmentalE2EAdapter:
    """A pure-stub ``EnvironmentalE2EPort`` facet -- every method is one raise."""

    def build(self, feature_root: Path) -> Path:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")

    def install(self, artifact: Path, prefix: Path) -> object:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")

    def run_against_installed(
        self, e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
    ) -> None:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")


class StubFixtureRobustnessDensityAdapter:
    """A pure-stub ``RobustnessDensityPort`` facet -- one unconditional raise."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")


class SyntheticLiarLanguageAdapterPlugin(LanguageAdapterPlugin):
    """Reproduces the feature's original registered-but-lying smoking gun.

    Declares all 3 ports ``True``; backs ``run_contract_gate`` with a genuine
    facet and ``verify_environmental_e2e`` / ``check_robustness_density``
    with pure stubs -- the shape the port-realization gate must flag,
    independent of any real shipped plugin's (mutable) implementation state.

    Abstract here (no ``target_language`` override) -- concrete zero-arg
    subclasses below fix the identifier so ``EntryPoint.load()()`` (a
    zero-arg construction) can resolve them.
    """

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        }

    def register_adapters(self, registry: Any) -> None:
        registry.register_contract_gate(
            _FIXTURE_TOOL_TOKEN, RealFixtureContractGateAdapter()
        )
        registry.register_environmental_e2e(
            _FIXTURE_TOOL_TOKEN, StubFixtureEnvironmentalE2EAdapter()
        )
        registry.register_robustness_density(
            _FIXTURE_TOOL_TOKEN, StubFixtureRobustnessDensityAdapter()
        )

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))


class SyntheticStubPytestFacetPlugin(LanguageAdapterPlugin):
    """A plugin that registers STUB e2e + density facets under ``"pytest"``.

    Used by the ADR-ULAR-005 seam-catch ATs (test_entry_point_registration_
    and_seam_guards.py scenarios 2-3): a Python target resolves the
    ``"pytest"`` tool-token, so the seam looks up its facet under that token.
    This plugin registers the pure-``NotImplementedError`` stub facets under
    ``"pytest"`` so the seam-catch has a registered stub to swallow --
    reproducing (as a CONTROLLED fixture) the shape the shipped
    ``NwaveLangPython`` plugin used to have before its facets were genuinely
    implemented. Discovered via a monkeypatched ``entry_points`` in the seam
    ATs, so the seed→discover→register→seam-catch path runs end-to-end.
    """

    @property
    def target_language(self) -> str:
        return "pytest-stub-fixture"

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        }

    def register_adapters(self, registry: Any) -> None:
        registry.register_environmental_e2e(
            "pytest", StubFixtureEnvironmentalE2EAdapter()
        )
        registry.register_robustness_density(
            "pytest", StubFixtureRobustnessDensityAdapter()
        )

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))


class SyntheticLiarLanguageAdapterPluginCSharp(SyntheticLiarLanguageAdapterPlugin):
    """Zero-arg concrete fixture plugin, ``target_language == "csharp"``."""

    @property
    def target_language(self) -> str:
        return "csharp"


class SyntheticLiarLanguageAdapterPluginKotlin(SyntheticLiarLanguageAdapterPlugin):
    """Zero-arg concrete fixture plugin, ``target_language == "kotlin"``."""

    @property
    def target_language(self) -> str:
        return "kotlin"


__all__ = [
    "CHECK_ROBUSTNESS_DENSITY",
    "RUN_CONTRACT_GATE",
    "VERIFY_ENVIRONMENTAL_E2E",
    "RealFixtureContractGateAdapter",
    "StubFixtureEnvironmentalE2EAdapter",
    "StubFixtureRobustnessDensityAdapter",
    "SyntheticLiarLanguageAdapterPlugin",
    "SyntheticLiarLanguageAdapterPluginCSharp",
    "SyntheticLiarLanguageAdapterPluginKotlin",
    "SyntheticStubPytestFacetPlugin",
]
