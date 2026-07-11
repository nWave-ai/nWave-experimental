"""Acceptance tests -- ``port_realization_discovery`` composition root (DISTILL, slice-02).

Feature-delta: docs/feature/language-port-realization-gate/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract + [REF] Slice Plan (slice-02)

Contract under test (DOES NOT EXIST YET -- active-RED by design):
``src/des/testarch/port_realization_discovery.py`` is a NEW composition-root
module (CREATE_NEW) that:

  1. Resolves the registered ``nwave.lang.adapter`` entry-points (or, for
     testability, accepts a caller-supplied ``plugins`` iterable directly --
     entry-point registration is explicitly NOT required for this slice, per
     the Slice Plan justification: "reads adapter source directly;
     entry-point registration NOT required; no recursion risk").
  2. For each ``LanguageAdapterPlugin`` instance, reads its self-declared
     ``port_coverage`` mapping.
  3. For each DECLARED-covered (``True``) port, locates the backing adapter
     method and AST-STUB-PROBES it: a method is a STUB iff
     ``inspect.getsource`` + ``ast.parse`` shows its body is reducible to a
     single ``raise NotImplementedError(...)`` (optional leading docstring
     only). Effect-Isolation (Earned-Trust 3-layer): this probe is STATIC --
     it must NEVER invoke ``build()``/``install()``/the probed method itself.
  4. Feeds ``{plugin_id: {port: declared}}`` + ``{plugin_id: {port: is_stub}}``
     to ``detect_port_realization_conformance`` (slice-01,
     ``des.testarch.rules.registry_conformance`` -- may ALSO be absent; this
     AT is active-RED on either or both missing pieces) and returns its
     verdict.

Signature this AT pins: ``resolve_and_probe_port_realization(plugins) ->
PortRealizationVerdict`` where ``plugins`` is an
``Iterable[LanguageAdapterPlugin]``.

Design pins this AT establishes for the composition root (necessary because
no prior slice fixed them):

  * ``PortRealizationViolation.plugin_id`` == the resolved plugin's
    ``target_language`` string (``"python"``, ``"typescript"``, ...) -- the
    only per-plugin identifier ``LanguageAdapterPlugin`` exposes; no
    entry-point name is available to key on instead (entry-point
    registration is out of this slice's scope).
  * To locate "the backing adapter method" for a declared-covered port
    without depending on a plugin's private tool-token, the discovery module
    must call ``plugin.register_adapters(registry)`` with a ``registry``
    object exposing ``register_contract_gate`` / ``register_environmental_e2e``
    / ``register_robustness_density`` (the exact three method names
    ``LanguageAdapterRegistry`` already exposes,
    ``src/des/adapters/driven/runner/runner_registry.py``) -- capturing
    whatever facet instance each call receives, independent of the ``name``
    (tool-token) argument the plugin passes. This AT's fixture plugins below
    call exactly those three method names, so ANY discovery implementation
    that duck-types against that surface (a private capturing double, or a
    real ``LanguageAdapterRegistry``) will resolve them.

Synthetic smoking gun (test-brittleness fix #92 -- SUPERSEDES the original
"read the shipped sources" verified smoking gun): scenarios 1-3 originally
drove the REAL shipped ``NwaveLangPython`` / ``NwaveLangTypescript`` plugins
directly, pinning the registered-but-lying shape to nWave-dev's OWN, mutable
adapter implementation state. Once ``implement-language-adapter-facets``
genuinely implemented ``{Python,TypeScript}EnvironmentalE2EAdapter`` /
``{Python,TypeScript}RobustnessDensityAdapter`` (no ``NotImplementedError``
remains in either), that premise silently went false and those scenarios
started failing for a STALE reason, not a regression. Scenarios 1-3 now
construct ``SyntheticLiarLanguageAdapterPlugin{CSharp,Kotlin}``
(``synthetic_language_adapter_fixtures.py``, this directory) -- a CONTROLLED
fixture reproducing the identical shape (all 3 ports declared ``True``;
``run_contract_gate`` genuinely implemented; ``verify_environmental_e2e`` +
``check_robustness_density`` pure ``raise NotImplementedError`` stubs) that
never depends on which language plugins nWave-dev itself ships or how
genuinely they are implemented.

Entry-point registration NOT required (Slice Plan justification): the
synthetic fixture plugins are never wired into ``pyproject.toml``'s
``nwave.lang.adapter`` group NOR does this AT require that -- it constructs
them directly and feeds them to the composition root's ``plugins`` argument,
bypassing ``importlib.metadata.entry_points`` entirely (real entry-point
discovery, if the crafter wires a default resolver behind ``plugins=None``,
is untested by this slice's AT -- out of scope per the justification above).

Active-RED scaffolding (hidden-import P1-P4, `nw-distill-red-scaffolding`):
the ENTIRE module ``des.testarch.port_realization_discovery`` is CREATE_NEW
(does not exist on disk at all yet), and it will itself import slice-01's
``detect_port_realization_conformance`` / ``PortRealizationVerdict`` from
``des.testarch.rules.registry_conformance`` -- which may ALSO be missing
(slice-01 in flight). A module-top ``from des.testarch import
port_realization_discovery`` would raise ``ModuleNotFoundError`` at
COLLECTION -> BROKEN, which the ``des verify-red-green`` seal REFUSES. So the
import lives INSIDE a hidden-import helper (``_load()``) each test body
calls, catching the broad ``ImportError`` family (covers both "module
entirely absent" and "module exists but its OWN import of slice-01 symbols
fails") and re-raising a semantic ``AssertionError`` (MISSING_FUNCTIONALITY)
-- active-RED, not BROKEN, regardless of which of the two missing pieces (or
both) is the cause.

Driving surface (Mandate-13 driving-port-only): the composition-root function
itself IS the driving port for this slice -- callers supply plain
``LanguageAdapterPlugin`` instances (fixtures below, or the real shipped
plugins), no subprocess, no live entry-point registry required.

CONTRACT_SHAPE: pure-function for every scenario in this module -- the
composition root is deterministic over its ``plugins`` argument (same plugin
instances + same on-disk adapter source => same verdict, always); it
performs an internal STATIC source read (``inspect.getsource`` +
``ast.parse``), never a mutation of caller-observable state, and -- the
Effect-Isolation invariant scenario 9 witnesses -- never invokes the probed
method itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from des.ports.language_adapter_plugin import LanguageAdapterPlugin, ProbeResult
from tests.build.language_port_realization_gate.acceptance.synthetic_language_adapter_fixtures import (
    SyntheticLiarLanguageAdapterPluginCSharp,
    SyntheticLiarLanguageAdapterPluginKotlin,
    SyntheticPartialStubLanguageAdapterPlugin,
)


if TYPE_CHECKING:
    from pathlib import Path


RUN_CONTRACT_GATE = "run_contract_gate"
VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"

# The two ports the real shipped plugins commit the registered-but-stubbed
# lie on (verified by reading the adapter sources above, before authoring).
_SHIPPED_STUB_LIE_PORTS = frozenset(
    {VERIFY_ENVIRONMENTAL_E2E, CHECK_ROBUSTNESS_DENSITY}
)

_REQUIRED_SYMBOLS = ("resolve_and_probe_port_realization",)


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3, `nw-distill-red-scaffolding`): the module
# does not exist yet at all (or its own slice-01 import fails), so the whole
# import -- module resolution AND name resolution -- is deferred to CALL
# TIME inside a test body. Collection stays green (COLLECT >= 1, the module
# top never names the absent module); the failure surfaces as a semantic
# AssertionError (MISSING_FUNCTIONALITY) -- active-RED, never a collection
# ImportError (BROKEN).
# ---------------------------------------------------------------------------


def _load() -> ModuleType:
    try:
        from des.testarch import port_realization_discovery as mod
    except ImportError as exc:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: "
            "src/des/testarch/port_realization_discovery.py does not exist yet "
            "(CREATE_NEW, feature-delta slice-02), OR it exists but its own "
            "import of slice-01's `detect_port_realization_conformance` / "
            "`PortRealizationVerdict` from "
            "des.testarch.rules.registry_conformance is not yet satisfied. "
            "Create the composition root exposing "
            "`resolve_and_probe_port_realization(plugins) -> "
            "PortRealizationVerdict` (resolving each plugin's `port_coverage`, "
            "AST-stub-probing each declared-covered port's backing adapter "
            "method via `plugin.register_adapters(<capturing registry>)`, and "
            "feeding both maps to the slice-01 pure detector) before this AT "
            f"can pass. Root cause: {exc}"
        ) from exc

    missing = [name for name in _REQUIRED_SYMBOLS if not hasattr(mod, name)]
    if missing:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: "
            "src/des/testarch/port_realization_discovery.py does not yet define "
            f"{missing}. Add `resolve_and_probe_port_realization(plugins) -> "
            "PortRealizationVerdict` per feature-delta slice-02 before this AT "
            "can pass."
        )
    return mod


def _offenders(verdict: object) -> set[tuple[str, str]]:
    return {(v.plugin_id, v.port) for v in verdict.violations}


# ---------------------------------------------------------------------------
# Fixture adapters -- each implements ONLY the RobustnessDensityPort's single
# method (`covered_domain_ids`), the natural single-method port for isolating
# the AST stub-detection PRIMITIVE from the multi-method-port composition
# already exercised by the real shipped plugins below (scenarios 1-3).
# ---------------------------------------------------------------------------


class _RealRobustnessAdapter:
    """A genuinely-implemented facet -- NOT reducible to a single raise."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        return {"real-domain"}


class _StubRobustnessAdapter:
    """A pure stub: body is exactly `raise NotImplementedError(...)`."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        raise NotImplementedError("fixture stub -- deliberately unimplemented")


class _DocstringLeadingStubRobustnessAdapter:
    """A stub preceded by a leading docstring ONLY -- still a pure stub."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        """Leading docstring only; the body is still reducible to one raise."""
        raise NotImplementedError("fixture stub with a leading docstring")


class _ConditionalStubRobustnessAdapter:
    """Raises NotImplementedError only CONDITIONALLY -- NOT a pure stub."""

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        if at_scope_dir is None:
            raise NotImplementedError("only when at_scope_dir is None")
        return set()


class _SideEffectRobustnessAdapter:
    """Mutates ``calls`` + raises a SENTINEL if actually CALLED.

    Proves Effect-Isolation: the probe must be STATIC
    (``inspect.getsource`` + ``ast.parse``) and must NEVER invoke the
    probed method. The sentinel ``RuntimeError`` is deliberately NOT a
    ``NotImplementedError`` so a caller that accidentally invokes this via a
    naive try/except-NotImplementedError probe still surfaces the call.
    """

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def covered_domain_ids(self, at_scope_dir: Path) -> set[str]:
        self._calls.append("covered_domain_ids-was-called")
        raise RuntimeError("SENTINEL: the probe must never CALL the target method")


class _FixtureRobustnessPlugin(LanguageAdapterPlugin):
    """Minimal fixture plugin declaring ONLY ``check_robustness_density``.

    Wires a caller-supplied ``RobustnessDensityPort``-shaped facet, isolating
    the AST stub-probe to a single-method port. ``register_adapters`` calls
    the exact three method names ``LanguageAdapterRegistry`` exposes
    (duck-typed against whatever capturing object the discovery module
    passes) -- mirrors ``NwaveLangPython``/``NwaveLangTypescript`` shape.
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

    def register_adapters(self, registry: object) -> None:
        registry.register_robustness_density("fixture-tool", self._adapter)  # type: ignore[attr-defined]

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, missing_ports=[], probed_at=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Scenario 1 -- the REAL smoking gun: the shipped NwaveLangPython /
# NwaveLangTypescript plugins each commit the registered-but-stubbed lie on
# exactly 2 of their 3 declared ports.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plugin_factory", "plugin_id"),
    [
        (SyntheticLiarLanguageAdapterPluginCSharp, "csharp"),
        (SyntheticLiarLanguageAdapterPluginKotlin, "kotlin"),
    ],
    ids=["csharp-synthetic-liar-plugin", "kotlin-synthetic-liar-plugin"],
)
def test_discovery_flags_a_synthetic_liar_plugins_declared_stub_backed_ports(
    plugin_factory: type[LanguageAdapterPlugin], plugin_id: str
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary (Ale: "I add csharp to the toml
    and the failures tell me what to implement").

    A CONTROLLED synthetic liar plugin declares `port_coverage[X]=True` for
    `verify_environmental_e2e` and `check_robustness_density` while both
    backing facets are pure `raise NotImplementedError` stubs -- discovery
    flags exactly those 2 ports, naming the plugin by `target_language`. The
    fixture is the SSOT for the stub-state (test-brittleness fix #92): the
    assertion is STABLE regardless of whether nWave-dev's own shipped
    Python/TypeScript facets are stubs or genuinely implemented.
    """
    plugin = plugin_factory()

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is True, (
        f"expected the synthetic {plugin_id} liar to be flagged: {verdict!r}"
    )
    assert _offenders(verdict) == {
        (plugin_id, VERIFY_ENVIRONMENTAL_E2E),
        (plugin_id, CHECK_ROBUSTNESS_DENSITY),
    }, verdict.violations


# ---------------------------------------------------------------------------
# Scenario 2 -- both synthetic liar plugins resolved together are flagged
# INDEPENDENTLY (mirrors slice-01's multi-plugin independence rule, now
# proven through the REAL composition root over two CONTROLLED fixtures).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_discovery_flags_both_synthetic_liar_plugins_independently_when_resolved_together() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    Resolving BOTH synthetic liar plugins in one call flags 4 violations
    total (2 per plugin) -- neither plugin's lie leaks onto, nor is masked
    by, the other.
    """
    verdict = _load().resolve_and_probe_port_realization(
        [
            SyntheticLiarLanguageAdapterPluginCSharp(),
            SyntheticLiarLanguageAdapterPluginKotlin(),
        ]
    )

    assert _offenders(verdict) == {
        ("csharp", VERIFY_ENVIRONMENTAL_E2E),
        ("csharp", CHECK_ROBUSTNESS_DENSITY),
        ("kotlin", VERIFY_ENVIRONMENTAL_E2E),
        ("kotlin", CHECK_ROBUSTNESS_DENSITY),
    }, verdict.violations
    assert len(verdict.violations) == 4, verdict.violations


# ---------------------------------------------------------------------------
# Scenario 3 -- NEGATIVE AT: the genuinely-implemented `run_contract_gate`
# port must NOT be flagged for either synthetic liar plugin, even though it
# is also declared True (guards against over-flagging every declared port).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_discovery_does_not_flag_the_genuinely_implemented_contract_gate_port_for_either_synthetic_liar_plugin() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    The synthetic liar plugin backs `run_contract_gate` with a genuine
    (non-stub) facet -- `run_contract_gate` must never appear among the
    violations for either plugin (WRONG outcome asserted absent).
    """
    verdict = _load().resolve_and_probe_port_realization(
        [
            SyntheticLiarLanguageAdapterPluginCSharp(),
            SyntheticLiarLanguageAdapterPluginKotlin(),
        ]
    )

    flagged_ports = {port for _plugin_id, port in _offenders(verdict)}
    assert RUN_CONTRACT_GATE not in flagged_ports, (
        f"run_contract_gate is genuinely implemented for both synthetic liar "
        f"plugins -- must not be flagged: {verdict.violations!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- AST correctness: a pure `raise NotImplementedError(...)` body
# IS a stub -> the declared+stub port is flagged.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_discovery_flags_a_declared_port_whose_backing_method_is_a_pure_notimplementederror_stub() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    A declared-covered port whose backing method body is exactly
    `raise NotImplementedError(...)` is a pure stub -- flagged.
    """
    plugin = _FixtureRobustnessPlugin("stub-lang", _StubRobustnessAdapter())

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is True
    assert _offenders(verdict) == {("stub-lang", CHECK_ROBUSTNESS_DENSITY)}


# ---------------------------------------------------------------------------
# Scenario 5 -- AST correctness: a leading docstring before the single raise
# is STILL a pure stub (per the design contract's explicit carve-out).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_discovery_flags_a_declared_port_whose_stub_has_a_leading_docstring_only() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    A body of [docstring, raise NotImplementedError(...)] is STILL a pure
    stub (the "optional leading docstring only" carve-out) -- flagged.
    """
    plugin = _FixtureRobustnessPlugin(
        "docstring-stub-lang", _DocstringLeadingStubRobustnessAdapter()
    )

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is True
    assert _offenders(verdict) == {("docstring-stub-lang", CHECK_ROBUSTNESS_DENSITY)}


# ---------------------------------------------------------------------------
# Scenario 6 -- NEGATIVE AT: a genuinely-implemented (non-stub) body must NOT
# be flagged, even though the port is declared True.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_discovery_does_not_flag_a_declared_port_with_a_real_non_stub_body() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    A declared-covered port whose backing method has a genuine (non-stub)
    body must NOT be flagged (WRONG outcome asserted absent).
    """
    plugin = _FixtureRobustnessPlugin("real-lang", _RealRobustnessAdapter())

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is False, (
        f"a genuinely-implemented body must not be flagged: {verdict.violations!r}"
    )
    assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 7 -- NEGATIVE AT: a CONDITIONAL `raise NotImplementedError` (not
# the entire body) is NOT a pure stub -- must NOT be flagged.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_discovery_does_not_flag_a_declared_port_whose_notimplementederror_is_conditional() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    A method that raises `NotImplementedError` only under a condition (not
    as its entire, unconditional body) is a real implementation with a
    partial-not-yet-supported branch, NOT a pure stub -- must NOT be flagged
    (WRONG outcome asserted absent; the AST-reducible-to-a-single-raise rule
    is exact, never a false positive on a conditional raise).
    """
    plugin = _FixtureRobustnessPlugin(
        "conditional-stub-lang", _ConditionalStubRobustnessAdapter()
    )

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is False, (
        f"a conditional NotImplementedError is not a pure stub -- must not "
        f"be flagged: {verdict.violations!r}"
    )
    assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 8 -- NEGATIVE AT: declaring False for a stub-backed port is
# HONEST, not a lie (mirrors slice-01's rule, now proven end-to-end through
# the real composition root's declared+stub AND-gate).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_discovery_does_not_flag_an_honestly_undeclared_port_even_if_its_backing_method_is_a_stub() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    A plugin declaring `port_coverage[check_robustness_density]=False` while
    its backing method IS a stub is being honest (it never claimed
    coverage) -- must NOT be flagged, even though the AST probe correctly
    classifies the method as a stub (WRONG outcome asserted absent).
    """
    plugin = _FixtureRobustnessPlugin(
        "honest-lang", _StubRobustnessAdapter(), declared=False
    )

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is False, (
        f"declaring False for an unimplemented port is honest, not a lie: "
        f"{verdict.violations!r}"
    )
    assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 9 -- NEGATIVE AT: Effect-Isolation. The probe must be STATIC --
# it must NEVER invoke the probed method (no `build()`/`install()`/target
# invocation, per the design contract).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_discovery_never_invokes_the_probed_adapter_method() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta [REF] Architecture & Contract
    (Effect-Isolation -- probing must NOT invoke `build()`/`install()`/the
    method itself).

    A fixture adapter whose method would mutate a caller-visible list AND
    raise a distinguishable sentinel IF actually called must show ZERO
    calls after discovery runs -- the probe reads source
    (`inspect.getsource` + `ast.parse`) only, it never executes the target
    (WRONG outcome -- the method being invoked -- asserted absent).
    """
    calls: list[str] = []
    plugin = _FixtureRobustnessPlugin(
        "side-effect-lang", _SideEffectRobustnessAdapter(calls)
    )

    _load().resolve_and_probe_port_realization([plugin])

    assert calls == [], (
        f"the AST stub-probe must be STATIC -- it must never CALL the "
        f"target method: {calls!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 10 -- boundary: an empty plugin list is trivially conformant.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_discovery_reports_an_empty_plugin_list_as_conformant() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary.

    No plugins supplied -> zero violations, conformant (never an error on
    the empty-input boundary).
    """
    verdict = _load().resolve_and_probe_port_realization([])

    assert verdict.flagged is False
    assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 11 -- REGRESSION (D1 false-negative, feature-end deep review):
# `_probe_port_is_stub` aggregates a multi-method port's per-method stub
# state with `all(is_stub_per_method)` -- a facet backing ONE method
# genuinely + the REST as pure stubs is classified NOT stub-backed, so a
# partially-registered port is never flagged. This DIRECTLY contradicts the
# feature's mission ("make partial-language-support IMPOSSIBLE"): a plugin
# author who implements `build()` alone, stubs `install()` +
# `run_against_installed()`, and declares
# `port_coverage[verify_environmental_e2e]=True` would PASS the gate today.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_discovery_rejects_conformance_for_a_declared_port_with_one_real_and_two_stub_methods() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta Summary ("make partial-language-support
    IMPOSSIBLE").

    A CONTROLLED synthetic plugin declares `verify_environmental_e2e=True`
    and backs it with a facet whose `build()` is genuinely implemented while
    `install()` / `run_against_installed()` remain pure
    `raise NotImplementedError` stubs -- 1 real method, 2 stub methods on a
    3-method port. The port MUST still be flagged (a partial registration is
    NOT conformant): declaring full coverage for a mostly-stubbed port is the
    same lie as declaring it for a fully-stubbed one, and the gate's `all()`
    aggregation must not let ONE genuine method launder the other two
    (WRONG outcome -- silent conformance on a partially-stubbed port --
    asserted absent).

    RED today: `_probe_port_is_stub` returns `all([False, True, True])` ==
    `False` for this facet, so `verify_environmental_e2e` is classified
    NOT stub-backed and `verdict.flagged` is `False` -- the gate wrongly
    reports this plugin CONFORMANT. Fix: `all` -> `any` in
    `src/des/testarch/port_realization_discovery.py::_probe_port_is_stub`
    (crafter's A_GREEN, not this AT).
    """
    plugin = SyntheticPartialStubLanguageAdapterPlugin()

    verdict = _load().resolve_and_probe_port_realization([plugin])

    assert verdict.flagged is True, (
        "a port backed by a facet with ONE real method and TWO stub methods "
        f"must be flagged as non-conformant (partial registration is not "
        f"conformant): {verdict!r}"
    )
    assert _offenders(verdict) == {("partial-stub-lang", VERIFY_ENVIRONMENTAL_E2E)}, (
        verdict.violations
    )
