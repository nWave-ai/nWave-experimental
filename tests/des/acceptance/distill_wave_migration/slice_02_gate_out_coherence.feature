@feature-f-distill-wave-migration @slice-02 @real-io @driving_port
Feature: A maintainer's design to AT divergence is caught at DISTILL gate-OUT and degrades loud
  # Slice-02 (feature-delta DESIGN Slice Plan FINAL: slice-02 carries AT-5..AT-8,
  # held AT the carpaccio ceiling 5, not split — one cohesive gate-OUT behavior).
  # The nw-distill skill normatively declares the gate-G review-rubric: the
  # design↔AT coherence witness at DISTILL gate-OUT and the §17 verdict mapping
  # (FAIL→redo-in-wave on an un-covered row; UNVERIFIED on a port-shaped surface
  # not yet on the contract / on suspected incompleteness; INDETERMINATE
  # degrade-LOUD when the mechanism cannot run; DEVOPS-induced scenarios
  # first-class). The real `des skill-normative-gate` dispatcher is the mechanical
  # witness that the prose carries each rule.
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real dispatcher over the
  # REAL shipped nWave/skills/nw-distill/SKILL.md. The AT asserts the SHIPPED exit
  # code — never a fabricated oracle.
  #
  # Active-RED (atdd_pure / ADR-025, NOT @skip): each rubric marker is ABSENT from
  # the shipped prose at HEAD → the real gate returns FAIL (exit 1) → these
  # scenarios expect PASS → AssertionError. DELIVER migrates the gate-G rubric +
  # §17 verdict mapping into nw-distill → the gate returns PASS → green.
  #
  # Mandate 9 v2: @real-io → example-based; no PBT machinery (Mandate 11).

  @contract-shape:unbounded-preservation @ac-5 @slice-02
  Scenario: The DISTILL skill declares DEVOPS-induced scenarios are first-class
    Given the real shipped DISTILL skill that carries the DEVOPS-induction rule exists
    And a clause asserting DEVOPS-induced scenarios are first-class and trace to the DEVOPS status
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing coherence clauses

  @contract-shape:unbounded-preservation @ac-6 @slice-02
  Scenario: The DISTILL skill declares an ambiguous port-shaped coupling is UNVERIFIED not a silent pass
    Given the real shipped DISTILL skill that carries the no-coupling rule exists
    And a clause asserting a port-shaped surface not yet on the contract is UNVERIFIED never a silent pass
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing coherence clauses

  @contract-shape:unbounded-preservation @ac-7 @slice-02
  Scenario: The DISTILL skill declares the gate-G review-rubric witnesses design to AT coherence
    Given the real shipped DISTILL skill that carries the gate-G coherence rubric exists
    And a clause asserting the gate-G review-rubric witnesses design to AT coherence at gate-OUT
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing coherence clauses

  @contract-shape:unbounded-preservation @ac-8 @slice-02
  Scenario: The DISTILL skill declares an unrunnable coherence mechanism degrades loud as INDETERMINATE
    Given the real shipped DISTILL skill that carries the degrade-loud rule exists
    And a clause asserting an unrunnable coherence mechanism is INDETERMINATE never a false green
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing coherence clauses
