@feature-f-design-wave-migration @slice-03
Feature: The advisory-skip-gate pattern is authored once as a reusable, citable anchor (AT-7)
  As a future wave-migration author who needs the same Tier-A advisory shape
  I want the advisory-skip-gate pattern authored once as a named, anchored,
    five-slot block that I can cite by anchor and bind to my own trigger
  So that the shape is SSOT — the five sibling wave-migrations extend it by
    reference, never re-inlining the pattern per trigger

  # slice-03 of f-design-wave-migration. AT AT-7 (the keystone deliverable).
  #
  # TEST-FORMAT CONVERSION: Gherkin form of the passing plain-pytest
  # test_slice03_reusable_pattern.py. The PRODUCTION pattern block already ships
  # GREEN in nw-distill, so these are GREEN-not-active-RED — the expected state for a
  # format conversion of passing behaviour. Each scenario stays GENUINE
  # (mutation-verifiable): removing the anchor heading, dropping a slot, or stripping
  # the row references in nw-distill/SKILL.md reds the scenario.
  #
  # DRIVING SURFACE (Mandate-13, prose-surface case): the filesystem read of the
  # REAL shipped nw-distill skill via the shared _skill_source helper, asserted on
  # DISCRIMINATING structural checks (the anchor heading + the five named slots
  # co-located in ONE window + the single-locus / cited-twice count).

  @slice-03 @driving_port @real-io @us-citable-anchor @contract-shape:unbounded-preservation
  Scenario: The pattern is authored as a named, citable anchor block
    When the shipped nw-distill skill is read
    Then nw-distill carries the named advisory-skip-gate pattern anchor block

  @slice-03 @driving_port @real-io @us-five-slots @contract-shape:unbounded-preservation
  Scenario: The pattern block carries the five Tier-A closed-option slots
    When the shipped nw-distill skill is read
    Then the pattern block carries the five Tier-A closed-option slots in its own body

  @slice-03 @driving_port @real-io @us-single-locus @contract-shape:unbounded-preservation
  Scenario: The pattern is a single authored locus referenced by both triggers
    When the shipped nw-distill skill is read
    Then the pattern is authored once and referenced by both the DESIGN-absent and total-AT triggers
