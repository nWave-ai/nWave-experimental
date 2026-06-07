# slice-03 — the conformance gate runs as part of the gate surface over the LIVE
# `nwave.lang.adapter` registry (language-adapter-registry-self-enforcement). Unlike
# slice-01 (which injects per-plugin realized surfaces) and slice-02 (which injects
# coverage frozensets), slice-03 is the LIVE-registry end-to-end vertical: the
# conformance gate CLI mode resolves-and-probes the ACTUAL registered plugins and
# enforces registry completeness mechanically, so no one must remember to maintain the
# catalog (DDD-D4a, C2 resolve-and-probe + C3 CLI mode + C5 gate-surface wiring).
#
# Three falsifiable-at-HEAD paths (DDD-D4a / DDD-D5), each a distinct exit lane on the
# `--check-conformance` mode of the existing validator CLI (DDD-D2 — one CLI, no sibling):
#
#   * RECALL / exit 1 (scenario 1) — the gate runs over the REAL registry via the real
#     CLI subprocess. At HEAD the only registered plugin is the inert `_conformance_fixture`
#     (realizes 0/9 required capabilities, `port_coverage={}`) — a GENUINE registered-but-
#     unrealized gap, not theater. The gate exits 1 and names a `(plugin, capability)` gap.
#     This is the live-registry end-to-end witness; it is falsifiable WITHOUT slice-05a
#     because the inert fixture is a real 0/9 gap at HEAD.
#   * LOUD INDETERMINATE / exit 3 (scenario 2) — when the discovery surface is
#     unresolvable (a registered entry point whose target module/class cannot be imported),
#     the gate emits a DISTINCT loud INDETERMINATE signal (exit 3, dedicated message),
#     NEVER a silent green and NEVER a fabricated empty discovery set (DDD-D5). Distinct
#     from the exit-1 gap lane and the exit-2 schema-invalid lane.
#   * PRECISION-CLEAN / exit 0 (scenario 3) — a frozen all-realized discovery result
#     (every discovered plugin realizes every required capability) → CONFORMANT, exit 0.
#     This pins the gate's clean exit lane WITHOUT claiming the LIVE registry is conformant
#     — the precision-live-CONFORMANT flip over the REAL registry is EXPLICITLY DEFERRED to
#     slice-05a (the real Python reference plugin). The gate correctly stays RED (exit 1) on
#     the inert live fixture; this scenario exercises the exit-0 mapping over an injected
#     clean result, never asserting the real registry is clean.
#
# Honest tagging (Mandate 9 v2): scenario 1 invokes the real CLI as a subprocess over the
# real `importlib.metadata` registry → @real-io @subprocess (example-based, never PBT).
# Scenario 2 drives the gate runner with an injected entry point whose `.load()` genuinely
# raises ModuleNotFoundError → @real-io (real resolution failure). Scenario 3 injects a
# frozen all-realized discovery RESULT (plain data, no `.load()`) → @in-memory. All
# example-based: a finite three-lane exit-code contract over a real/injected registry, not
# an unbounded generated domain.

@feature-language-adapter-registry-self-enforcement @slice-03
Feature: The methodology maintainer's conformance gate runs over the live registry as part of the gate surface

  As the methodology maintainer
  I want the conformance gate to resolve-and-probe the actual registered language-adapter
  plugins at gate time and flag any registered-but-unrealized capability, degrade loudly
  when a plugin cannot be resolved, and report a clean registry as conformant
  So that registry completeness is enforced mechanically and no one must remember to keep
  the catalog in lock-step with the registered plugins

  @slice-03 @real-io @subprocess @contract-shape:unbounded-preservation
  Scenario: The conformance gate over the live registry flags a registered plugin that omits a required capability
    Given the conformance gate is invoked over the live language-adapter registry
    When the maintainer runs the conformance gate
    Then the conformance gate reports a registered-but-unrealized capability gap
    And the conformance gate names the registered-but-unrealized capability gap
    And the conformance gate leaves the registry and catalog unchanged

  @slice-03 @real-io @contract-shape:unbounded-preservation
  Scenario: The conformance gate degrades loudly when a registered plugin cannot be resolved
    Given a registered language-adapter plugin whose discovery surface cannot be resolved
    When the maintainer runs the conformance gate over the unresolvable registry
    Then the conformance gate reports an indeterminate discovery failure
    And the conformance gate does not report the registry as conformant

  @slice-03 @in-memory @contract-shape:unbounded-preservation
  Scenario: The conformance gate reports a registry in which every plugin realizes every capability as conformant
    Given a registry result in which every discovered plugin realizes every required capability
    When the maintainer runs the conformance gate over the clean registry result
    Then the conformance gate reports the registry as conformant
