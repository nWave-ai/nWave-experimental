@feature-d4-phase-2-workflow-flavors
Feature: classic.yaml flavor config validates + distinct primitive composition

  As nWave maintainer authoring the classic fallback flavor
  I want `nWave/flavors/classic.yaml` to:
    1. Validate against the flavor schema
    2. Reference only catalog gates
    3. Demonstrate INV-11: same primitive set as atdd_pure, different composition
  So that classic and atdd_pure prove flavor pattern empirically
  And future flavors (framework-shipped) follow the same pattern

  Background:
    Given the workflow flavor YAML loader is available

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: classic.yaml validates against flavor schema
    Given the flavor file at "nWave/flavors/classic.yaml"
    And the flavor schema at "nWave/flavors/_schema.yaml"
    When the flavor is validated against the schema
    Then validation succeeds with zero errors

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function
  Scenario: Every classic gate_id exists in catalog (shares atdd_pure primitive set per INV-11)
    Given the flavor file at "nWave/flavors/classic.yaml"
    And the gate catalog at "nWave/gates/_catalog.yaml"
    When the gate references are extracted from lifecycle_events
    Then every referenced gate_id matches a catalog entry

  @driving_port @in-process @real-io @slice-02 @contract-shape:pure-function @regression-pin
  Scenario: classic uses classic-mode gates (roadmap + log-phase) distinct from atdd_pure
    Given the flavor file at "nWave/flavors/classic.yaml"
    When classic-specific gate references are extracted
    Then the classic flavor uses gate "roadmap" in dispatch.pre
    And the classic flavor uses gate "log-phase" in subagent.stop
    And the classic flavor uses gate "verify-integrity" in feature.end
    And the classic flavor does NOT reference gate "carpaccio-slice-gate"
