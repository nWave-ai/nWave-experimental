@feature-f-distill-wave-migration @slice-01 @walking_skeleton @real-io @driving_port
Feature: A maintainer running DISTILL induces the acceptance tests from the design contract
  # Slice-01 walking skeleton (feature-delta DESIGN Slice Plan FINAL: slice-01
  # carries AT-1..AT-4). The thinnest end-to-end vertical proving the JOB-025
  # "induce-not-reinvent" job: the nw-distill skill normatively declares that
  # AT structure is INDUCED from the design contract via the 3-source map, and
  # the real `des skill-normative-gate` dispatcher is the mechanical witness that
  # the prose carries that declaration.
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real `des
  # skill-normative-gate` dispatcher reads the REAL shipped
  # nWave/skills/nw-distill/SKILL.md and emits PASS/FAIL/INDETERMINATE. The AT
  # asserts the SHIPPED exit code — never a fabricated oracle (protocol-driver
  # contract: the oracle is the gate's real exit code over the real file).
  #
  # Active-RED (atdd_pure / ADR-025, NOT @skip): each f-distill induction marker
  # is ABSENT from the shipped prose at HEAD → the real gate returns FAIL (exit 1)
  # → these scenarios expect PASS → AssertionError. DELIVER migrates the induction
  # map into nw-distill → the gate returns PASS → green.
  #
  # Mandate 9 v2: @real-io (real subprocess + real filesystem) → example-based;
  # no PBT machinery (Mandate 11).

  @contract-shape:unbounded-preservation @ac-1 @slice-01
  Scenario: The DISTILL skill declares that ATs are induced from the design contract
    Given the real shipped DISTILL skill that DISTILL consumes the design contract from exists
    And a clause asserting the DISTILL skill declares ATs are induced from the design contract
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing induction clauses

  @contract-shape:unbounded-preservation @ac-2 @slice-01
  Scenario: The DISTILL skill declares the example-table row to scenario bijection
    Given the real shipped DISTILL skill that carries the example-table correspondence exists
    And a clause asserting every example-table row maps to exactly one scenario
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing induction clauses

  @contract-shape:unbounded-preservation @ac-3 @slice-01
  Scenario: The DISTILL skill declares the contract-shape to treatment mapping
    Given the real shipped DISTILL skill that carries the contract-shape treatment exists
    And a clause asserting a declared law induces a property test and an error-encoding a sad path
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing induction clauses

  @contract-shape:unbounded-preservation @ac-4 @slice-01
  Scenario: The DISTILL skill declares ATs are scaffolded per-slice active-RED never skipped
    Given the real shipped DISTILL skill that carries the slice-plan scaffolding rule exists
    And a clause asserting ATs are scaffolded per-slice active-RED never skipped
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing induction clauses
