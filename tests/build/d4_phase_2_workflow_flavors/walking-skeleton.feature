@feature-d4-phase-2-workflow-flavors
Feature: atdd_pure.yaml flavor config validates + references catalog gates

  As nWave maintainer authoring D4 Phase 2 atdd_pure flavor
  I want `nWave/flavors/atdd_pure.yaml` to:
    1. Validate against the flavor schema (Phase 1 slice-03)
    2. Reference only gates that exist in the Phase 1 slice-01 catalog
    3. Capture the current `carpaccio_intercept.py` dispatch.pre composition
  So that Phase 3 (D2 dispatcher refactor) has byte-equivalence target

  Background:
    Given the workflow flavor YAML loader is available

  @walking_skeleton @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: atdd_pure.yaml validates against flavor schema
    Given the flavor file at "nWave/flavors/atdd_pure.yaml"
    And the flavor schema at "nWave/flavors/_schema.yaml"
    When the flavor is validated against the schema
    Then validation succeeds with zero errors

  @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: Every gate_id referenced in atdd_pure.yaml exists in the catalog
    Given the flavor file at "nWave/flavors/atdd_pure.yaml"
    And the gate catalog at "nWave/gates/_catalog.yaml"
    When the gate references are extracted from lifecycle_events
    Then every referenced gate_id matches a catalog entry

  @driving_port @in-process @real-io @slice-01 @contract-shape:unbounded-preservation @regression-pin
  Scenario: atdd_pure dispatch.pre composition captures carpaccio-slice-gate as primary gate
    Given the flavor file at "nWave/flavors/atdd_pure.yaml"
    When the dispatch.pre composition is read
    Then the composition contains the gate "carpaccio-slice-gate"
    And the gate carries on_failure equal to "block"
    And the gate args reference feature_id and entering_slice placeholders
