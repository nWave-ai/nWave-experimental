@feature-fix-design-component-manifest
Feature: The design-exit review enforces the component manifest end to end

  The final slice wires the manifest into the design wave's exit review so a
  design wave cannot finish without a validated, grounded manifest, and registers
  the gate in the framework catalog so its firing -- and its waiver rate -- are
  visible. It also ships the reviewer-check protocol that instructs the reviewer
  to judge declaration correctness, the one check no tool can make.

  Read in sequence after slice-04: slice-04 made the manifest produced; this
  slice makes its absence or wrongness block the design wave from exiting.

  # Layer 3 (FS acceptance) -- example-based, no PBT universe (wiring slice).
  # AT3 is a presence check on the reviewer-check protocol document (W1 / B2):
  # it asserts the protocol names the semantic veto item -- it does NOT test the
  # veto judgment itself, which has no deterministic oracle.

  @slice-05 @driving_port @wiring_e2e @contract-shape:bounded-change
  Scenario: A design wave is blocked from exiting on an ungrounded manifest
    Given a feature whose design directory has been prepared
    And the architect has written a manifest naming a symbol absent from its file
    When the design-exit review checks the component manifest
    Then the design wave is blocked from exiting

  @slice-05 @contract-shape:unbounded-preservation
  Scenario: The component manifest gate is registered and its waiver rate is visible
    Given the design wave's framework assets
    Then the framework catalog registers the component manifest gate
    And the catalog exposes a countable not-applicable waiver signal

  @slice-05 @contract-shape:unbounded-preservation
  Scenario: The reviewer-check protocol names the declaration-correctness veto
    Given the design wave's framework assets
    Then a reviewer-check protocol document exists
    And the protocol names the declaration-correctness check as a reviewer veto
