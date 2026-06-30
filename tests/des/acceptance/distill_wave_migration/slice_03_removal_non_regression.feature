@feature-f-distill-wave-migration @slice-03 @infrastructure @real-io @driving_port
Feature: The legacy non-inducing DISTILL prose is removed and the keystone floor is not regressed
  # Slice-03 (feature-delta DESIGN Slice Plan FINAL: removal-only, @infrastructure,
  # AT-9 = absence + non-regression). The deliverable is the ABSENCE of stale
  # non-inducing AT-authoring prose (C8/G-1/G-3) plus the NON-REGRESSION witness
  # that the keystone's DESIGN-absent→advisory reconciliation (C7/G-4) is
  # preserved. There is no new driving behaviour to specify — per the removal-only
  # slice contract, per-slice positive @slice ATs are N/A; this slice's witnesses
  # are absence + floor-preservation, driven through the same real gate port.
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real `des
  # skill-normative-gate` dispatcher over the REAL shipped
  # nWave/skills/nw-distill/SKILL.md. The AT asserts the SHIPPED exit code.
  #
  # ABSENCE semantics: a clause registers the LEGACY marker; the gate FAILs when a
  # marker is ABSENT. Absence is the desired end state, so the AT asserts FAIL.
  # TODAY the legacy prose is still present → the gate returns PASS → the AT
  # (expecting FAIL) is ACTIVE-RED (atdd_pure / ADR-025, NOT @skip). DELIVER removes
  # the legacy prose → the gate returns FAIL → green.
  #
  # NON-REGRESSION semantics (C7/G-4): the keystone-reconciled DESIGN-absent
  # advisory wording MUST stay present (gate PASS). This is a floor-preservation
  # guard — green now and must remain green across the migration; it pins that
  # f-distill's edits EXTEND the keystone floor and never re-introduce a block.
  #
  # Mandate 9 v2: @real-io → example-based; no PBT machinery (Mandate 11).

  @contract-shape:unbounded-preservation @ac-9-absence @slice-03
  Scenario: The legacy non-inducing AT-authoring prose is absent from the DISTILL skill
    Given the real shipped DISTILL skill that the legacy prose is removed from exists
    And a clause registering the legacy non-inducing AT-authoring marker
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is FAIL with exit code 1 because the legacy marker is absent
    And the verdict names the legacy non-inducing clause

  @contract-shape:unbounded-preservation @ac-9-non-regression @slice-03
  Scenario: The keystone DESIGN-absent advisory floor is preserved not regressed to a block
    Given the real shipped DISTILL skill that carries the keystone advisory floor exists
    And a clause asserting the DESIGN-absent advisory floor wording is preserved
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0 because the advisory floor is preserved
