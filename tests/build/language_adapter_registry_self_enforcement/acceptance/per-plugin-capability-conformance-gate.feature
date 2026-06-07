# slice-01 — the per-plugin x per-capability conformance gate (the walking-skeleton
# vertical; language-adapter-registry-self-enforcement, DDD-D3a plugin-axis ruling).
#
# The slice-12 ``detect_real_adapter_capability_conformance`` detector GENERALIZED
# from 1-D (registered capabilities x ONE real adapter method-surface) to the 2-D
# cross-product (registered capabilities x EVERY registered plugin's realized
# surface). The thinnest drift->RED vertical: a registered language-adapter plugin
# that omits a registered capability is flagged RED by the generalized gate.
#
# slice-01 tests the PURE 2-D rule (C1) over INJECTED surfaces — it does NOT read the
# live ``nwave.lang.adapter`` registry (that is C2, slice-03 / DDD-D4a). This mirrors
# slice-12 exactly: slice-12 injects ``CompleteFixtureAdapter`` / a frozen drifted
# snapshot; slice-01 injects a frozen ``{plugin_id: realized_map}`` (recall + frozen
# precision) plus the real ``PythonAstAdapter`` method-surface as the de-facto
# reference realized map (precision-live, the falsifiable flip).
#
# Recall/precision golden-fixture shape (DDD-D3a, the shape every Tier-S gate uses):
#
#   * RECALL (scenario 1) — drives the 2-D detector against the FROZEN unrealized-pair
#     snapshot that PERMANENTLY carries a registered-but-unrealized (plugin, capability)
#     pair. Asserts FLAGGED + the named offender pair. Green forever once the detector
#     exists — proves the 2-D gate CAN bite.
#   * PRECISION on a frozen all-realized snapshot (scenario 2) — drives the detector
#     against the FROZEN all-realized snapshot (every plugin realizes every required
#     capability). Asserts CONFORMANT — proves the gate does NOT over-fire (the
#     fail-closed precision bar, the clean_ golden complement).
#   * PRECISION-LIVE (scenario 3) — drives the detector against the real
#     ``PythonAstAdapter`` method-surface INJECTED as a single-element realized map
#     (the de-facto reference adapter; the required-capability set read live from the
#     registry). Asserts CONFORMANT. ``PythonAstAdapter`` realizes all 9 required
#     capabilities, so injected-as-a-realized-map it is conformant — the witness that
#     flips RED->GREEN EXACTLY when A_GREEN implements the 2-D detector (C1). NOT an
#     assertion that ``PythonAstAdapter`` is a registered nwave.lang.adapter plugin
#     (it isn't; the live registry read is slice-03's concern).
#
# Honest tagging: an in-process introspection of the testarch substrate —
# @component (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn,
# no real I/O.

@feature-language-adapter-registry-self-enforcement @slice-01 @walking-skeleton @component
Feature: The methodology maintainer sees a registered plugin that omits a registered capability flagged at author-time

  As the methodology maintainer
  I want a registered language-adapter plugin that omits a registered capability to be
  flagged by the generalized per-plugin conformance gate, while both a frozen
  all-realized snapshot and the injected reference adapter are reported conformant
  So that registry-to-plugin capability drift becomes red-at-author-time across every
  registered plugin, not only the one adapter the slice-12 gate already checked

  Background:
    Given the generalized per-plugin capability conformance gate

  @slice-01 @walking-skeleton @coupled @contract-shape:pure-function
  Scenario: A frozen snapshot where a plugin omits a registered capability is flagged
    When the maintainer checks the frozen snapshot with an unrealized capability pair
    Then the gate flags a plugin-capability gap in the snapshot
    And the gate names the plugin and the capability the plugin does not realize

  @slice-01 @walking-skeleton @coupled @contract-shape:pure-function
  Scenario: A frozen snapshot where every plugin realizes every capability is cleared
    When the maintainer checks the frozen snapshot where every plugin is fully realized
    Then the gate reports every plugin as realizing every registered capability

  @slice-01 @walking-skeleton @coupled @contract-shape:pure-function
  Scenario: The injected reference adapter realizes every registered capability
    When the maintainer checks the injected reference adapter surface
    Then the gate reports every plugin as realizing every registered capability
