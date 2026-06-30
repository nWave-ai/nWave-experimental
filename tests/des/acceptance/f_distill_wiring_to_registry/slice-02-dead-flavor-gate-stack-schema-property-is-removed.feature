@feature-f-distill-wiring-to-registry
Feature: The dead flavor gate-stack schema property is removed from the shipped schema

  slice-02 completes the MOVE-not-COPY: once the registry (nWave/waves/*.yaml) is
  the SOLE gate-stack source and no flavor instance carries a wave_gate_stacks
  block, the flavor SCHEMA property that allowed those blocks is dead and must go
  too. This is f-distill slice-02's OWN deliverable (DDD-9) -- the SCHEMA-level
  twin of slice-01's flavor-INSTANCE removal. A surviving dead schema property
  re-opens the door to a dormant flavor co-tenant the spine never reads.

  @slice-02 @driving_port @contract-shape:bounded-change @CS-1
  Scenario: The dead flavor gate-stack property is absent from the shipped schema
    Given the shipped flavor schema
    When the flavor schema is inspected for the dead gate-stack property
    Then the dead flavor gate-stack property is absent
