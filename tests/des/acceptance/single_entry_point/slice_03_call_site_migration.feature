@feature_fix_des_single_entry_point_consolidation @slice-03
Feature: slice-03 — every repo-internal caller uses the new des invocation

  Unparked 2026-05-24 (N2 night autonomous PRR push). Architect's slice-03 ATs
  (AT-07, AT-08, AT-09) per feature-delta.md.

  These ATs are CLASS-LEVEL assertions (grep-zero across trees), not per-site
  enumeration. The actionable rewrite sites (architect estimated ~58;
  empirically ~80 after the 5-shim retirement + scoping refinement) do NOT
  each get an AT — three assertions cover them all because the test grep
  covers them all.

  Background:
    Given the nwave runtime is installed

  @skip @contract-shape:unbounded-preservation @adapter-integration @real-io
  # TEMP @skip per friction #50 baseline-dirty 2026-05-26 — 10 legacy
  # `python -m des.cli.X` refs remain in tests/ (e2e, installer/, bugs/).
  # Migration scope is broader than slice-03 anticipated. Un-skip when
  # tests/ migration completes via dedicated follow-up slice.
  Scenario: No runtime-authoring tree references the legacy module-form invocation
    When the migration scan inspects the runtime-authoring trees for module-form references
    Then the migration scan finds zero occurrences of the legacy module-form invocation
    And the migration scan excludes its own pattern declaration

  @contract-shape:unbounded-preservation @adapter-integration @real-io
  Scenario: No runtime-authoring tree references the legacy des-prefixed console scripts
    When the migration scan inspects the runtime-authoring trees for the five legacy console-script names
    Then the migration scan finds zero occurrences of the legacy console-script names
    And the migration scan excludes its own pattern declaration

  @contract-shape:bounded-change @driving_port @real-io @adapter-integration
  Scenario: The packaged console-script surface contains the dispatcher and excludes legacy shims
    When the package contract test inspects the shipped console-script entries
    Then the shipped entries include the installer entry and the des dispatcher entry
    And no des-prefixed legacy entry remains in the package surface
