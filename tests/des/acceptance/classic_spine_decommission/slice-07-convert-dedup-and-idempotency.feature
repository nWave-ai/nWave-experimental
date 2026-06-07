@feature-classic-spine-decommission
Feature: An architect's conversion is deduplicated and idempotent
  As a solution architect retiring the classic roadmap spine
  I want a step committed twice to count once and a re-run conversion to be
    idempotent via the journal
  So that an entry-gate restart and a repeated run never corrupt the conversion

  # slice-07 of classic-spine-decommission. S6: a step committed twice after an
  # entry-gate restart is deduplicated by SHA. C4: re-running a conversion on an
  # already-converted feature is idempotent via the journal.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (main(argv)).

  # --- S6: a step committed twice is deduplicated by SHA -----------------------

  @slice-07 @driving_port @contract-shape:bounded-change
  Scenario: A step committed twice after an entry-gate restart yields one shipped slice
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "04-01" constitute slice "slice-04"
    And step "04-01" was committed at "dddd444" whose commit exists and is reachable with green tests
    And step "04-01" appears committed twice at the same commit "dddd444"
    When the architect converts the feature
    Then slice "slice-04" is reconciled as shipped

  # --- C4 idempotency: the journalled resumable execute ------------------------

  @slice-07 @driving_port @contract-shape:unbounded-preservation
  Scenario: Converting an already-converted feature is idempotent via the journal
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    When the architect converts the feature
    And the architect converts the feature a second time
    Then the conversion journal is unchanged by the second run
    And the feature is never left half-converted
