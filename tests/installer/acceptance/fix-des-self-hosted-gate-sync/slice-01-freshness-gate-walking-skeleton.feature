@feature-fix-des-self-hosted-gate-sync @slice-01 @walking_skeleton
# Feature: DES freshness gate — walking-skeleton
# Story: bootstrap paradox closure (D2 P0)
# Slice: 01 — gate exists, fires on `import des.cli`, distinguishes
#        DEGRADED (no manifest) from state A (customer, no repo) AND honors
#        the NWAVE_FRESHNESS=skip env-var opt-out (F3 bootstrap-blind closure
#        for repo's everyday dev-tree usage; option A scope-expansion pulled
#        from slice-03 per Crafter-A escalation 2026-05-23, ratified by Ale).
# Design SSOT: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md
# Architect DDDs: 1, 2, 6, 7, 9, 10, 12, + DDD-10 (NWAVE_FRESHNESS opt-out
# spec) and DDD-5 (install plugin's own bypass usage).
# Residuality anchors: F3 bootstrap-blind = AT-01-B + AT-01-C (both legs).
#
# State machine the gate enforces (§1.3 four-state truth table):
#   (no install manifest) ------------> DEGRADED → REFUSE, exit 78
#   (manifest, source unreachable) ---> A         → PROCEED, exit 0
#   (manifest, commit mismatch) ------> D         → REFUSE  [slice-02 covers]
#   (manifest, content match) --------> C         → PROCEED [slice-02 covers]
#
# Env-var opt-out short-circuit (§1.8 + DDD-10), exercised by AT-01-C:
#   NWAVE_FRESHNESS=skip --------------> PROCEED, exit 0, structured WARN line
#                                        `des.runtime.freshness.skipped` on
#                                        stderr (load-bearing audit evidence).
#   Holds across ALL truth-table rows, including DEGRADED-no-manifest —
#   the install plugin and repo dev usage rely on this bypass.
#
# Composition root (Pillar 3): freshness_probe.spawn_gate_against(installed)
# wraps `python -c "import des.cli"` against a synthetic installed tree under
# tmp_path, so the production composition root (`des.cli/__init__.py`) runs
# end-to-end — only the filesystem witnesses are tmp-scoped.
#
# Universe per Mandate 8: {exit_code, stderr_event, stderr_state, verdict}.
# Internal fields (subprocess Popen handle, stdin file) NEVER appear.

Feature: DES freshness gate refuses stale installs and proceeds for customers
  As a developer running `python -m des.cli.*` against a self-hosted DES
  I want the gate to REFUSE when the installed copy has no install manifest
  And to PROCEED silently when no repo is reachable (customer install)
  So that the bootstrap paradox is mechanically closed at the import boundary

  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: Operator runs a CLI against an installed tree without manifest
    Given a synthetic installed DES tree at the standard install path
    And the installed tree has no `_install_manifest.json`
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate REFUSES the invocation with exit code 78
    And the gate emits a structured event `des.runtime.freshness.refused`
    And the gate reports state DEGRADED

  @walking_skeleton @driving_port @real-io @slice-01 @customer @contract-shape:unbounded-preservation
  Scenario: Customer install on a host with no repository PROCEEDS silently
    Given a synthetic installed DES tree at the standard install path
    And the installed tree carries a manifest whose `source_tree` is not reachable
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate PROCEEDS the invocation with exit code 0
    And no structured event is emitted on standard error

  @slice-01 @driving_port @real-io @adapter-integration @opt-out @contract-shape:bounded-change
  Scenario: Operator opts out via NWAVE_FRESHNESS=skip and the gate honors the bypass
    Given a synthetic installed DES tree at the standard install path
    And the installed tree has no `_install_manifest.json`
    And the operator sets the freshness opt-out to skip
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate PROCEEDS the invocation with exit code 0
    And the gate emits a structured event `des.runtime.freshness.skipped`
    And no refusal is reported on standard error
