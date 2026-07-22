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

from des.ports.driven_ports.environmental_e2e_port import EnvironmentalE2EPort
from des.ports.driven_ports.robustness_density_port import RobustnessDensityPort
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


class MixedRealAndStubEnvironmentalE2EAdapter:
    """A 3-method ``EnvironmentalE2EPort`` facet with ONE real method + TWO stubs.

    Regression fixture for the D1 false-negative (feature-end deep review,
    ``language-port-realization-gate``): ``_probe_port_is_stub``
    (``src/des/testarch/port_realization_discovery.py:184-213``) aggregates a
    multi-method port's per-method stub-state with
    ``return all(is_stub_per_method)`` -- a port is classified stub-backed
    ONLY when EVERY one of its backing methods is a pure stub. This facet
    backs ``build()`` with a genuine implementation while ``install()`` and
    ``run_against_installed()`` remain pure ``raise NotImplementedError``
    stubs -- 1 real / 2 stub. ``all([False, True, True])`` is ``False``, so
    today's probe classifies this facet as NOT stub-backed and the gate
    reports the declaring plugin CONFORMANT, even though 2 of the port's 3
    methods are fake. A future plugin author could implement `build()` alone,
    stub the remaining two methods, declare
    `port_coverage[verify_environmental_e2e]=True`, and PASS the gate --
    exactly the partial-language-support hole this feature exists to close.
    """

    def build(self, feature_root: Path) -> Path:
        return feature_root / "fixture-artifact"

    def install(self, artifact: Path, prefix: Path) -> object:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")

    def run_against_installed(
        self, e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
    ) -> None:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")


class SyntheticPartialStubLanguageAdapterPlugin(LanguageAdapterPlugin):
    """Declares ``verify_environmental_e2e=True``, backed by a MIXED real+stub facet.

    Reproduces the D1 false-negative regression shape (see
    ``MixedRealAndStubEnvironmentalE2EAdapter``): a single declared-covered,
    MULTI-method port where only SOME of its backing methods are stubs. The
    other two ports are honestly declared ``False`` so the scenario isolates
    the mixed-stub aggregation bug from the all-or-nothing per-port shape
    ``SyntheticLiarLanguageAdapterPlugin`` already exercises.
    """

    @property
    def target_language(self) -> str:
        return "partial-stub-lang"

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: False,
        }

    def register_adapters(self, registry: Any) -> None:
        registry.register_environmental_e2e(
            _FIXTURE_TOOL_TOKEN, MixedRealAndStubEnvironmentalE2EAdapter()
        )

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))


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


# ===========================================================================
# STUB-EVASION SHAPE FAMILY (fix-port-realization-stub-evasion, slice-01)
# ===========================================================================
#
# One fixture per SHAPE a maintainer might plausibly write behind a claimed
# capability, so that catching one shape can never mask a blind spot in
# another (charter: "do not settle for one probe ... probe each shape
# individually"). Nearly all use the SINGLE-method
# ``check_robustness_density`` port (``RobustnessDensityPort.covered_domain_ids``)
# so each fixture isolates the classification PRIMITIVE rather than the
# multi-method aggregation the ``...EnvironmentalE2E...`` fixtures above
# already exercise.
#
# Two families:
#   * EVASION-*  -- a do-nothing body in some spelling; MUST be flagged.
#   * HONEST-*   -- genuine, if tiny, real work; MUST NOT be flagged.
#
# Deliberately NOT represented as evasions (known-accepted residuals, RCA):
# a constant return faking success (``return {"fake"}``) and a log-only
# single-``Expr(Call)`` body -- the SHIPPED
# ``PythonEnvironmentalE2EAdapter.run_against_installed`` IS a single
# ``Expr(Call)``, so any rule excluding that shape would fire on production
# code. Both appear below on the HONEST side instead.
# ---------------------------------------------------------------------------


class EvasionEllipsisThenRaiseRobustnessAdapter:
    """EVASION A -- a bare ``...`` line, THEN ``raise NotImplementedError``.

    The *ordinary* Python spelling of "not implemented yet" (charter Intent:
    "this is the shape a real maintainer is most likely to write").
    """

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        ...
        raise NotImplementedError("fixture evasion A -- deliberately unimplemented")


class EvasionSilentReturnNoneRobustnessAdapter:
    """EVASION B1 -- silently returns ``None``; never raises, never works."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return None  # type: ignore[return-value]


class EvasionSilentPassRobustnessAdapter:
    """EVASION B2 -- body is only ``pass``; never raises, never works."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        pass  # type: ignore[return-value]


class EvasionSilentEllipsisRobustnessAdapter:
    """EVASION B3 -- body is only a bare ``...``; never raises, never works."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:  # type: ignore[empty-body]
        ...


class EvasionSilentBareReturnRobustnessAdapter:
    """EVASION B4 -- body is only a bare ``return``; never raises, never works."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return  # type: ignore[return-value]


class EvasionReturnNotImplementedRobustnessAdapter:
    """EVASION B5 -- returns the ``NotImplemented`` sentinel instead of raising."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return NotImplemented  # type: ignore[return-value]


class EvasionDocstringOnlyRobustnessAdapter:
    """EVASION D -- the body is ONLY a docstring; never raises, never works."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:  # type: ignore[empty-body]
        """Return the domain ids tagged by a ``# domain: <id>`` marker."""


class EvasionRuntimeErrorRaiseRobustnessAdapter:
    """EVASION E -- unconditionally raises a NON-``NotImplementedError`` type."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        raise RuntimeError("not implemented yet")


class EvasionInheritedProtocolRobustnessAdapter(RobustnessDensityPort):
    """EVASION C -- subclasses the REAL ``RobustnessDensityPort``, overrides NOTHING.

    Not adversarial: inheriting the Protocol for type-checker help is the
    natural thing a well-meaning author does. ``getattr(type(facet),
    "covered_domain_ids")`` then resolves to the PROTOCOL's own
    ``[docstring, ...]`` body
    (``src/des/ports/driven_ports/robustness_density_port.py``), so the facet
    claims the capability while implementing none of it.
    """


class EvasionInheritedProtocolEnvironmentalE2EAdapter(EnvironmentalE2EPort):
    """EVASION C (multi-method) -- subclasses ``EnvironmentalE2EPort``, overrides NOTHING.

    The RCA's named worst case: all three methods (``build`` / ``install`` /
    ``run_against_installed``) resolve to the Protocol's ``[docstring, ...]``
    bodies (``src/des/ports/driven_ports/environmental_e2e_port.py:41-57``),
    so NO method of the declared-covered port is implemented at all.
    """


class EvasionMethodAbsentRobustnessAdapter:
    """EVASION F -- a registered facet that does not define the port's method at all."""

    def some_unrelated_helper(self) -> str:
        return "not the port's method"


def _real_domain_ids_helper(at_scope_dir: Path) -> set[str]:
    """Collaborator standing in for genuine per-language work."""
    return {f"domain-from-{at_scope_dir.name}"}


class HonestDelegatingRobustnessAdapter:
    """HONEST -- a one-line delegation to a real collaborator."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return _real_domain_ids_helper(at_scope_dir)


class HonestAttributeReturnRobustnessAdapter:
    """HONEST -- returns state held on the facet; thin, but real."""

    def __init__(self, ids: set[str] | None = None) -> None:
        self._ids = ids if ids is not None else {"honest-domain"}

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return self._ids


class HonestSideEffectingCallRobustnessAdapter:
    """HONEST -- a single side-effecting ``Expr(Call)`` body.

    Mirrors the SHIPPED ``PythonEnvironmentalE2EAdapter.run_against_installed``
    (``src/des/adapters/driven/e2e/python_environmental_e2e_adapter.py``),
    whose whole body is one delegating call. A rule that treated a lone
    ``Expr(Call)`` as "no work" would fire on production code.
    """

    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:  # type: ignore[empty-body]
        self._sink.append(str(at_scope_dir))


class HonestConstantReturnRobustnessAdapter:
    """HONEST (known-accepted residual) -- returns a constant success value.

    The RCA deliberately does NOT close this: a constant return still counts
    as evidence of work. Pinned here so a future over-correction that starts
    flagging constant returns is caught as a precision regression, not
    silently accepted.
    """

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return {"constant-domain"}


class HonestConditionalRaiseRobustnessAdapter:
    """HONEST -- a raise nested inside ``if``, with real work around it.

    A guard-clause raise is ordinary defensive code, not a stub. Mirrors the
    existing ``_ConditionalStubRobustnessAdapter`` scenario in
    ``test_port_realization_discovery.py``, whose verdict must not change.
    """

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        if at_scope_dir is None:
            raise ValueError("at_scope_dir is required")
        return _real_domain_ids_helper(at_scope_dir)


class HonestTryExceptRaiseRobustnessAdapter:
    """HONEST -- a raise nested inside ``try``/``except``, wrapping real work."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        try:
            return _real_domain_ids_helper(at_scope_dir)
        except OSError as exc:
            raise RuntimeError(f"cannot read {at_scope_dir}") from exc


class HonestEarlyReturnRobustnessAdapter:
    """HONEST -- an early-return guard followed by real work."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        if not at_scope_dir.name:
            return set()
        return _real_domain_ids_helper(at_scope_dir)


class HonestDocstringThenWorkRobustnessAdapter:
    """HONEST -- a leading docstring followed by genuine work."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        """Return the domain ids tagged by a ``# domain: <id>`` marker."""
        return _real_domain_ids_helper(at_scope_dir)


class HonestRealEnvironmentalE2EAdapter:
    """HONEST -- all three ``EnvironmentalE2EPort`` methods do real work."""

    def build(self, feature_root: Path) -> Path:
        return feature_root / "honest-artifact"

    def install(self, artifact: Path, prefix: Path) -> object:
        return prefix / artifact.name

    def run_against_installed(
        self, e2e_path: Path, prefix: Path, junit_path: Path, work_dir: Path
    ) -> None:
        """Delegate to a collaborator -- a single side-effecting call."""
        junit_path.write_text(f"{e2e_path}|{prefix}|{work_dir}", encoding="utf-8")


class SyntheticShapeProbeRobustnessPlugin(LanguageAdapterPlugin):
    """Declares ONLY ``check_robustness_density``, backed by a caller-supplied facet.

    One knob per axis (plugin id, backing facet, declared-or-not) so a single
    ``@pytest.mark.parametrize`` can drive the whole shape family through the
    real gate without a bespoke plugin class per shape.
    """

    def __init__(
        self, plugin_id: str, adapter: object, *, declared: bool = True
    ) -> None:
        self._plugin_id = plugin_id
        self._adapter = adapter
        self._declared = declared

    @property
    def target_language(self) -> str:
        return self._plugin_id

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: False,
            CHECK_ROBUSTNESS_DENSITY: self._declared,
        }

    def register_adapters(self, registry: Any) -> None:
        registry.register_robustness_density(_FIXTURE_TOOL_TOKEN, self._adapter)

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))


class SyntheticShapeProbeEnvironmentalE2EPlugin(LanguageAdapterPlugin):
    """Declares ONLY ``verify_environmental_e2e``, backed by a caller-supplied facet."""

    def __init__(
        self, plugin_id: str, adapter: object, *, declared: bool = True
    ) -> None:
        self._plugin_id = plugin_id
        self._adapter = adapter
        self._declared = declared

    @property
    def target_language(self) -> str:
        return self._plugin_id

    @property
    def port_coverage(self) -> dict[str, bool]:
        return {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: self._declared,
            CHECK_ROBUSTNESS_DENSITY: False,
        }

    def register_adapters(self, registry: Any) -> None:
        registry.register_environmental_e2e(_FIXTURE_TOOL_TOKEN, self._adapter)

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))


__all__ = [
    "CHECK_ROBUSTNESS_DENSITY",
    "RUN_CONTRACT_GATE",
    "VERIFY_ENVIRONMENTAL_E2E",
    "EvasionDocstringOnlyRobustnessAdapter",
    "EvasionEllipsisThenRaiseRobustnessAdapter",
    "EvasionInheritedProtocolEnvironmentalE2EAdapter",
    "EvasionInheritedProtocolRobustnessAdapter",
    "EvasionMethodAbsentRobustnessAdapter",
    "EvasionReturnNotImplementedRobustnessAdapter",
    "EvasionRuntimeErrorRaiseRobustnessAdapter",
    "EvasionSilentBareReturnRobustnessAdapter",
    "EvasionSilentEllipsisRobustnessAdapter",
    "EvasionSilentPassRobustnessAdapter",
    "EvasionSilentReturnNoneRobustnessAdapter",
    "HonestAttributeReturnRobustnessAdapter",
    "HonestConditionalRaiseRobustnessAdapter",
    "HonestConstantReturnRobustnessAdapter",
    "HonestDelegatingRobustnessAdapter",
    "HonestDocstringThenWorkRobustnessAdapter",
    "HonestEarlyReturnRobustnessAdapter",
    "HonestRealEnvironmentalE2EAdapter",
    "HonestSideEffectingCallRobustnessAdapter",
    "HonestTryExceptRaiseRobustnessAdapter",
    "MixedRealAndStubEnvironmentalE2EAdapter",
    "RealFixtureContractGateAdapter",
    "StubFixtureEnvironmentalE2EAdapter",
    "StubFixtureRobustnessDensityAdapter",
    "SyntheticLiarLanguageAdapterPlugin",
    "SyntheticLiarLanguageAdapterPluginCSharp",
    "SyntheticLiarLanguageAdapterPluginKotlin",
    "SyntheticPartialStubLanguageAdapterPlugin",
    "SyntheticShapeProbeEnvironmentalE2EPlugin",
    "SyntheticShapeProbeRobustnessPlugin",
    "SyntheticStubPytestFacetPlugin",
]
