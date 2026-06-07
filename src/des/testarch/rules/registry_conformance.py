"""Drift-guard conformance rules for the testarch substrate (ADR-TEST-002 slice-12).

slice-12 (created by DISTILL, implemented by DELIVER). Two CONFORMANCE rules that
turn the registry/vocabulary drift this feature exists to prevent on the feature's
OWN testarch substrate (Earned-Trust self-application, ADR-TEST-002 D-C/D-E):

  1. **Layer-value-coverage** — every ``Layer`` value that ANY rule names in a
     classification set MUST be adapter-producible: present in the reference
     adapter's producible-layer surface (``_SEGMENT_TO_LAYER.values()``). A rule
     referencing a layer value the adapter never emits is an unreachable-by-
     construction classification — a value-blind drift the existing slice-02
     conformance check (which validates capability METHOD NAMES, never enum VALUES)
     cannot see.

  2. **Real-adapter capability conformance** — every REGISTERED ``Capability``
     member MUST have a backing method on the REAL adapter (the production adapter
     the gates actually dispatch through), NOT only on a test-double. A capability
     registered but with no real-adapter method is registered-but-unrealized —
     method-name-blind for production: the slice-02 self-test stays green against
     the FIXTURE while the production adapter is non-conformant.

**Parametrized by design (ADR-TEST-002 D-E golden-fixture meta-rule).** Both
``detect`` functions take their inputs as ARGUMENTS — the classification sets +
the producible-layer surface for #1, the registered capability members + the
adapter method-name surface for #2. This lets the gate be pointed at EITHER:

  * a FROZEN golden-fixture snapshot that permanently carries the drift (the
    RECALL witness — proves the gate CAN bite; green forever); OR
  * the LIVE production surface read at runtime (the PRECISION witness — proves the
    real substrate is drift-free; RED while the live surface carries drift, GREEN
    after A_GREEN cleans it).

The detectors are PURE over their arguments — they hard-read NO live internal. The
composition root supplies the live surface (read, never transcribed) for the
precision scenario and the frozen fixture for the recall scenario. This is the same
recall-frozen / precision-live shape every Tier-S gate (slices 01-09) uses, here
applied to the substrate itself.

Unlike the Tier-S AST rules (M1/M8/M9/CM-I/M2/P3), these rules do NOT dispatch
through ``TestSuiteAstAdapter`` — they cross-check vocabulary surfaces supplied as
plain data (a conformance test OF the testarch package's own vocabulary, not a
language-agnostic rule over test-suite source). The ADR-TEST-002 D-A no-``import
ast`` constraint binds the Tier-S source-scanning rules; this self-conformance gate
names no parser API at all.

Both ``detect`` functions cross-check the supplied vocabulary surfaces. The
PRECISION scenario additionally relied on A_GREEN cleaning the live surface (drop
``fs_acceptance`` from the two forbidden/audited sets; remove the
registered-but-unrealized caps ``string_literals_in_call`` +
``parametrize_arg_source`` from the ``Capability`` enum + registry) — now done, so
the live substrate is conformant in both vocabulary dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


# The breach-kind names the verdicts report (the port-exposed ``Violation.kind``
# strings). Domain constants — kept in lock-step with the acceptance vocabulary's
# ``ConformanceBreachKind`` enum values.
LAYER_VALUE_NOT_ADAPTER_PRODUCIBLE_BREACH = "layer_value_not_adapter_producible"
CAPABILITY_NOT_REALIZED_ON_REAL_ADAPTER_BREACH = (
    "capability_not_realized_on_real_adapter"
)

# The breach-kind the 2-D per-plugin x per-capability detector reports
# (language-adapter-registry-self-enforcement slice-01, DDD-D3a). A registered
# capability with no backing method on a registered language-adapter plugin's
# realized surface is a per-plugin-unrealized capability.
CAPABILITY_NOT_REALIZED_BY_PLUGIN_BREACH = "capability_not_realized_by_plugin"


@dataclass(frozen=True)
class LayerValueViolation:
    """A flagged Layer-value-coverage breach (port-exposed observable).

    ``rule_set`` — the name of the classification set that references the
                   non-producible layer value (e.g.
                   ``pbt_layer_mode.PBT_FORBIDDEN_LAYERS``).
    ``layer_value`` — the ``Layer.value`` string referenced but never produced by
                   the reference adapter (e.g. ``"fs_acceptance"``).
    ``kind`` — ``"layer_value_not_adapter_producible"``.
    """

    rule_set: str
    layer_value: str
    kind: str


@dataclass(frozen=True)
class CapabilityRealizationViolation:
    """A flagged real-adapter capability-conformance breach (port-exposed observable).

    ``capability`` — the ``Capability.value`` string registered but not realized as
                   a method on the real adapter (e.g. ``"string_literals_in_call"``).
    ``kind`` — ``"capability_not_realized_on_real_adapter"``.
    """

    capability: str
    kind: str


@dataclass(frozen=True)
class LayerValueCoverageVerdict:
    """The Layer-value-coverage rule's port-exposed result.

    ``violations`` — every non-adapter-producible layer reference (empty ==
                     conformant: every referenced layer value is producible).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[LayerValueViolation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@dataclass(frozen=True)
class CapabilityRealizationVerdict:
    """The real-adapter capability-conformance rule's port-exposed result.

    ``violations`` — every registered-but-unrealized capability (empty ==
                     conformant: every registered capability is realized on the
                     real adapter).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[CapabilityRealizationViolation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


def detect_layer_value_coverage(
    classification_sets: Mapping[str, Iterable[str]],
    producible_layers: Iterable[str],
) -> LayerValueCoverageVerdict:
    """Flag every layer value a classification set references that is not producible.

    ``classification_sets`` maps a rule-set name (e.g.
    ``"pbt_layer_mode.PBT_FORBIDDEN_LAYERS"``) to the ``Layer.value`` strings that
    set references. ``producible_layers`` is the set of ``Layer.value`` strings the
    reference adapter can actually produce (its ``_SEGMENT_TO_LAYER.values()``). A
    referenced value the adapter cannot produce is an unreachable-by-construction
    classification — the drift this rule converts from human-caught to
    RED-at-author-time.

    PURE over its arguments — the composition root supplies EITHER a frozen fixture
    snapshot (recall) OR the live production surface read at runtime (precision).

    Emits a ``LayerValueViolation`` per ``(rule_set, layer_value)`` whose
    ``layer_value`` is not in ``producible_layers``.
    """
    producible = frozenset(producible_layers)
    violations = tuple(
        LayerValueViolation(
            rule_set=rule_set,
            layer_value=layer_value,
            kind=LAYER_VALUE_NOT_ADAPTER_PRODUCIBLE_BREACH,
        )
        for rule_set, referenced_values in classification_sets.items()
        for layer_value in referenced_values
        if layer_value not in producible
    )
    return LayerValueCoverageVerdict(violations=violations)


def detect_real_adapter_capability_conformance(
    registered_capabilities: Iterable[str],
    adapter_method_names: Iterable[str],
) -> CapabilityRealizationVerdict:
    """Flag every registered capability with no backing method on the real adapter.

    ``registered_capabilities`` is the set of ``Capability.value`` strings the
    registry declares. ``adapter_method_names`` is the set of method names the real
    adapter exposes. A registered capability whose value is not among the adapter's
    method names is registered-but-unrealized — method-name-blind for production
    (green against a test-double, non-conformant in production).

    PURE over its arguments — the composition root supplies EITHER a frozen fixture
    snapshot (recall) OR the live ``Capability`` enum + real ``PythonAstAdapter``
    method surface read at runtime (precision).

    Emits a ``CapabilityRealizationViolation`` per registered capability whose value
    is not in ``adapter_method_names``.
    """
    realized = frozenset(adapter_method_names)
    violations = tuple(
        CapabilityRealizationViolation(
            capability=capability,
            kind=CAPABILITY_NOT_REALIZED_ON_REAL_ADAPTER_BREACH,
        )
        for capability in registered_capabilities
        if capability not in realized
    )
    return CapabilityRealizationVerdict(violations=violations)


# ===========================================================================
# 2-D per-plugin x per-capability conformance (RED SCAFFOLD — A_GREEN implements)
# ===========================================================================
#
# language-adapter-registry-self-enforcement slice-01 (DDD-D3a). The GENERALIZATION
# of ``detect_real_adapter_capability_conformance`` from the 1-D form (one registered-
# capability set x ONE adapter method-name surface) to the 2-D cross-product (one
# registered-capability set x EVERY registered plugin's realized method-name
# surface). The 1-D form above is PRESERVED verbatim (M-2 / slice-12 AT stays green);
# this is an ADDITIVE sibling in the same module (EXTEND-in-module, DDD-D3).
#
# Like the 1-D form it is PURE over its arguments and import-``ast``-free — the
# composition root supplies EITHER a frozen ``{plugin_id: realized_map}`` snapshot
# (recall / frozen precision) OR the real reference-adapter method-surface injected
# as a single-element realized map (precision-live, DDD-D3a). The live ``entry_points``
# registry read is a SEPARATE composition-root concern (C2), tested in slice-03
# (DDD-D4a) — never inside this pure detector.


@dataclass(frozen=True)
class PerPluginCapabilityViolation:
    """A flagged per-plugin x per-capability breach (port-exposed observable).

    ``plugin_id`` — the registered plugin id whose realized surface omits the
                    capability (e.g. ``"ghost_plugin"`` in the frozen recall
                    corpus, or a registered ``nwave.lang.adapter`` plugin id once
                    the live read lands in slice-03).
    ``capability`` — the registered ``Capability.value`` string the plugin does
                    not realize (e.g. ``"imports_in_module"``).
    ``kind`` — ``"capability_not_realized_by_plugin"``.
    """

    plugin_id: str
    capability: str
    kind: str


@dataclass(frozen=True)
class PerPluginCapabilityVerdict:
    """The 2-D per-plugin x per-capability rule's port-exposed result.

    ``violations`` — every registered-but-unrealized ``(plugin, capability)`` pair
                     (empty == conformant: every registered plugin realizes every
                     registered capability).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[PerPluginCapabilityViolation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


def detect_per_plugin_capability_conformance(
    required_capabilities: Iterable[str],
    realized_by_plugin: Mapping[str, Iterable[str]],
) -> PerPluginCapabilityVerdict:
    """Flag every ``(plugin, capability)`` pair a plugin is required to but does not realize.

    ``required_capabilities`` is the registered-capability obligation set (the
    ``Capability.value`` strings the registry declares — the SAME SSOT the 1-D form
    consumes). ``realized_by_plugin`` maps each registered plugin id to the
    capability-method names that plugin realizes. A registered capability absent from
    a plugin's realized surface is a registered-but-unrealized ``(plugin, capability)``
    pair — the per-plugin generalization of the 1-D method-name-blind drift.

    PURE over its arguments — the composition root supplies EITHER a frozen
    ``{plugin_id: realized_map}`` snapshot (recall / frozen precision) OR the real
    reference-adapter method-surface injected as a single-element realized map
    (precision-live, DDD-D3a). Never reads the live ``entry_points`` registry (that is
    the C2 composition-root concern, slice-03 / DDD-D4a).

    Emits a ``PerPluginCapabilityViolation`` per ``(plugin_id, capability)`` whose
    ``capability`` is in ``required_capabilities`` but not in that plugin's realized
    surface, in a stable order (plugins in insertion order, capabilities in the order
    they appear in ``required_capabilities``).
    """
    required = tuple(required_capabilities)
    violations = tuple(
        PerPluginCapabilityViolation(
            plugin_id=plugin_id,
            capability=capability,
            kind=CAPABILITY_NOT_REALIZED_BY_PLUGIN_BREACH,
        )
        for plugin_id, realized_surface in realized_by_plugin.items()
        for capability in required
        if capability not in frozenset(realized_surface)
    )
    return PerPluginCapabilityVerdict(violations=violations)


# --- slice-02: catalog coverage-drift cross-check (C4) ----------------------
#
# language-adapter-registry-self-enforcement, slice-02 (DISTILL, per-slice JIT).
# A DIFFERENT cross-check from the per-plugin x capability detector above: this one
# compares the catalog's DECLARED coverage (the hand-authored ``supported-languages``
# set + the catalog's ``ports`` set) against the DISCOVERED plugins' actual coverage
# (the registered plugins' ``target_language`` set + their covered-port set). The
# "remember to maintain the catalog" hazard (ARCH_TECH_DEBT.md:61) becomes a mechanical
# RED: when the hand-authored declaration drifts from what the registry actually
# provides, the gate flags it.
#
# Drift conditions (RED when ANY holds):
#   * the declared language set != the discovered ``target_language`` set (either
#     direction — over-declaration OR under-declaration), OR
#   * a discovered covered port falls OUTSIDE the catalog's declared ports.
#
# PURE over its arguments (DDD-D6 / DDD-D2): the composition root (the
# ``--check-coverage-drift`` CLI mode in ``validate_language_adapter_catalog.py``)
# performs the LIGHT discovery — reads each registered plugin's ``target_language`` +
# ``port_coverage`` keys via ``entry_points(group="nwave.lang.adapter")`` — and the
# catalog read, then hands this rule four plain-data frozensets. This rule never reads
# the registry, the filesystem, or imports ``ast``. The slice-02 light discovery is the
# ``target_language``/``port_coverage``-key read ONLY — NOT the C2 capability
# resolve-and-probe-method-surface (that is slice-03).
#
# RED scaffold (Mandate-7 / ADR-025): raises ``AssertionError`` (the RED token — NOT
# NotImplementedError, NOT ImportError) until A_GREEN implements it.

CATALOG_LANGUAGE_COVERAGE_DRIFT_BREACH = "catalog_language_coverage_drift"
"""``kind`` for a declared-vs-discovered ``target_language`` set mismatch."""

PORT_OUTSIDE_CATALOG_BREACH = "covered_port_outside_catalog"
"""``kind`` for a discovered covered port absent from the catalog's declared ports."""


@dataclass(frozen=True)
class CoverageDriftViolation:
    """A flagged catalog coverage-drift breach (port-exposed observable).

    ``detail`` — the specific drifted token: a language id (for a declared-vs-
                 discovered language mismatch) or a port id (for an out-of-catalog
                 covered port).
    ``kind`` — one of ``CATALOG_LANGUAGE_COVERAGE_DRIFT_BREACH`` /
               ``PORT_OUTSIDE_CATALOG_BREACH``.
    """

    detail: str
    kind: str


@dataclass(frozen=True)
class CoverageDriftVerdict:
    """The catalog coverage-drift cross-check's port-exposed result.

    ``violations`` — every drifted language/port token (empty == conformant: the
                     declared coverage matches the discovered coverage AND no covered
                     port falls outside the catalog).
    ``flagged``    — True iff at least one drift was found (the RED signal).
    """

    violations: tuple[CoverageDriftViolation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


def detect_catalog_coverage_drift(
    declared_languages: Iterable[str],
    discovered_languages: Iterable[str],
    catalog_ports: Iterable[str],
    covered_ports: Iterable[str],
) -> CoverageDriftVerdict:
    """Flag catalog coverage drift against the discovered plugins' actual coverage.

    ``declared_languages`` is the catalog's hand-authored ``supported-languages`` set;
    ``discovered_languages`` is the registered plugins' ``target_language`` set (LIGHT
    discovery — read at the composition root). ``catalog_ports`` is the catalog's
    declared ``port-id`` set; ``covered_ports`` is the union of the registered plugins'
    ``port_coverage`` keys. A language present in exactly one of the declared/discovered
    sets is a coverage drift; a covered port absent from the catalog is an out-of-catalog
    port. Either is RED.

    PURE over its arguments — never reads the registry, the filesystem, or ``ast``.
    """
    declared = frozenset(declared_languages)
    discovered = frozenset(discovered_languages)
    catalog = frozenset(catalog_ports)
    covered = frozenset(covered_ports)
    language_violations = tuple(
        CoverageDriftViolation(
            detail=language,
            kind=CATALOG_LANGUAGE_COVERAGE_DRIFT_BREACH,
        )
        for language in declared ^ discovered
    )
    port_violations = tuple(
        CoverageDriftViolation(
            detail=port,
            kind=PORT_OUTSIDE_CATALOG_BREACH,
        )
        for port in covered - catalog
    )
    return CoverageDriftVerdict(violations=language_violations + port_violations)
