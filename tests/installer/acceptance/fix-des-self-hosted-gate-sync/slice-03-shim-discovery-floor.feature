@feature-fix-des-self-hosted-gate-sync @slice-03
# Feature: DES shim discovery — regression floor
# Story: drift-across-boundary (F1) closure for CLI module enumeration
# Slice: 03 — `_discover_shims(<src/des/cli>)` returns a superset of the
#        `DES_SHIMS_FLOOR` frozen regression constant (the canonical CLI
#        module set every spine dispatch depends on).
# Design SSOT: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md
#              §2.2 Addition 2 + DDD-4 (architect's AT-03-A, SPLIT-isolated
#              to its own slice 2026-05-23 by DISTILL — was the first row
#              of the original 13-AT slice-03 that exceeded the carpaccio
#              ceiling 3).
#
# Closure shape (per DDD-4):
#   The hand-maintained `DES_SHIMS = [...]` constant in `DESPlugin`
#   historically lagged behind reality — the install missed CLI modules
#   (verify_environmental_e2e, verify_slice_commit_completeness,
#   run_contract_gate) that were added to `src/des/cli/` but not to the
#   constant. Slice-03 closes the class:
#
#   - `_discover_shims(source_dir)` (new helper in `scripts/install/plugins/`)
#     globs the source-tree CLI directory and emits one shim per module.
#     Filesystem is the SSOT.
#   - `DES_SHIMS_FLOOR` (new frozen set in the same module) names the
#     canonical CLI modules every spine dispatch transitively depends on.
#     Floor never shrinks. Drift detection is mechanical: a missing module
#     under `src/des/cli/` reds the test.
#
# Layer: 3 (integration) — the AT invokes the production helper directly
# on the real `src/des/cli/` directory. No subprocess (the contract under
# test is a pure-function-shape glob + set-membership check; spawning a
# subprocess would only add cost, no signal).
#
# Composition root (Pillar 3): the AT instantiates no in-memory double —
# it calls the production helper against the real repo's `src/des/cli/`
# directory, exactly as the install plugin will at install time. The test
# IS the production-shape invocation. State-delta universe is the discovered
# set's superset relationship to the floor — single port-exposed observable.
#
# Universe per Mandate 8 (layer-3 + pure-function shape — universe-guard is
# OPTIONAL at layer 3+ per Mandate 8 fine print, but applied here for
# consistency with slice-01/02): {discovery.superset_of_floor: bool}.

Feature: DES install plugin discovers CLI shims from the source-tree filesystem
  As the install plugin
  I want `_discover_shims(<src/des/cli>)` to enumerate every CLI module on disk
  And the discovery to be a superset of `DES_SHIMS_FLOOR` (regression floor)
  So that newly-added CLI modules ship automatically and the install never
  silently drops a load-bearing CLI

  @slice-03 @driving_port @adapter-integration @contract-shape:unbounded-preservation
  Scenario: Discovery returns a superset of the DES_SHIMS_FLOOR regression constant
    Given the production source tree at `src/des/cli` is the discovery target
    When the install plugin discovers shims from that directory
    Then the discovered shims are a superset of the `DES_SHIMS_FLOOR` constant
    And the production source tree is unchanged
