@feature-f-design-wave-migration @slice-01
Feature: DISTILL surfaces a DESIGN-absent advisory that never blocks (row 7b)
  As an operator running DISTILL on a feature that skipped the DESIGN wave
  I want nw-distill to advise me of the duplication / incoherent-architecture risk
    and propose /nw-design
  So that I am aware of the gap by design, yet the flow always proceeds to DISTILL
    on any answer (the soft-gate never blocks)

  # slice-01 (walking skeleton) of f-design-wave-migration. ATs AT-1 / AT-2 / AT-5.
  #
  # TEST-FORMAT CONVERSION: this is the Gherkin form of the passing plain-pytest
  # test_slice01_design_skip_advisory.py. The PRODUCTION prose (row 7b in
  # nw-distill) already ships GREEN — these scenarios are GREEN-not-active-RED, the
  # expected state for a format conversion of passing behaviour. Each scenario stays
  # GENUINE (mutation-verifiable): perturbing row 7b's window in nw-distill/SKILL.md
  # reds the scenario.
  #
  # DRIVING SURFACE (Mandate-13, prose-surface case): the filesystem read of the
  # REAL shipped nw-distill skill via the shared _skill_source helper. The
  # DESIGN-skip soft-gate is LLM-reads-markdown-prose behaviour with no runtime code
  # path; the deterministic, git-free, cross-OS observable is the shipped skill's
  # row-7b prose, asserted on DISCRIMINATING multi-word phrases windowed around the
  # [REF] Code-Design anchor (not an incidental mention elsewhere).

  @slice-01 @walking_skeleton @driving_port @real-io @us-design-absent @contract-shape:unbounded-preservation
  Scenario: DESIGN-absent advisory exists and proposes the DESIGN wave
    When the shipped nw-distill skill is read
    Then nw-distill keys a DESIGN-absent advisory off the missing Code-Design section
    And the advisory proposes the DESIGN wave as the remedy

  @slice-01 @driving_port @real-io @us-design-absent @contract-shape:unbounded-preservation
  Scenario: The advisory fires on absence and stays silent on presence
    When the shipped nw-distill skill is read
    Then the advisory branches on absence versus presence and is silent when DESIGN is present

  @slice-01 @driving_port @real-io @us-never-blocks @contract-shape:unbounded-preservation
  Scenario: The advisory always proceeds to DISTILL and never blocks
    When the shipped nw-distill skill is read
    Then the advisory proceeds to DISTILL on any answer and never blocks
