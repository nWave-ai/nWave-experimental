@feature-rigor-review-step-toggles
Feature: Priya sees an honest rigor surface with no dead mutation knob
  As Priya, an nWave operator reading the rigor configuration surface
  I want the per-feature mutation_enabled knob removed wherever it is exposed
  So that nothing implies per-feature mutation control when mutation is
     actually CI-nightly-only (project strategy nightly-delta)

  # slice-05 (DD-D2, @infrastructure, removal-only): rigor_mutation_enabled has
  # ZERO production readers (audited; independently re-confirmed via Tsunami
  # callers_of = 0). It is REMOVED, not wired, from:
  #   (a) the DESConfig property (des_config.py ~L415)
  #   (b) the nw-rigor SKILL.md profile table + Mode-3 Step-7 + comparison/detail
  #       views (5 literal "mutation_enabled" occurrences at HEAD: L31/220/240/
  #       274/391)
  # No schema scenario: ZERO config-schema files (step-tdd-cycle-schema.json,
  # atdd-pure-phase-sequence.schema.json) list the token -- confirmed by grep --
  # so an absence-assertion there would be a vacuous green, not active-RED, and
  # is intentionally omitted (would not fail today).
  #
  # Driving surfaces (real, in-process, hermetic -- no interpreter fork, no
  # ~/.claude path):
  #   (a) a REAL DESConfig over a real tmp_path/.nwave/des-config.json -- the
  #       SAME in-process config-adapter surface slices 01-04 drive.
  #   (b) a REAL file read of the shipped nWave/skills/nw-rigor/SKILL.md.
  #
  # RED today because the knob still exists; GREEN once DELIVER deletes it.

  @slice-05 @infrastructure @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: The config reader no longer exposes a per-feature mutation knob
    Given a project rigor configuration surface backed by a real DESConfig
    When the rigor configuration surface is inspected for the mutation knob
    Then the config reader exposes no rigor_mutation_enabled accessor

  @slice-05 @infrastructure @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: The shipped rigor guide no longer documents a mutation knob row
    Given the shipped nw-rigor quality-profile guide
    When the rigor guide is inspected for the mutation knob token
    Then the rigor guide contains no mutation_enabled token
