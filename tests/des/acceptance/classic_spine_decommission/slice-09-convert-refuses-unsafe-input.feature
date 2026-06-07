@feature-classic-spine-decommission
Feature: An architect's conversion refuses a degraded resource cleanly
  As a solution architect retiring the classic roadmap spine
  I want the converter to refuse a non-writable feature directory, leaving the
    feature untouched
  So that a degraded resource never corrupts a feature mid-conversion

  # slice-09 of classic-spine-decommission. C7a: a non-writable feature
  # directory is refused cleanly, leaving the feature and its classic artifacts
  # intact.
  #
  # NOTE (feature-end-review consolidation): this slice previously also carried
  # a stale-manifest-row refusal scenario. That scenario passed only against a
  # hand-written fixture manifest the production classifier can never emit
  # (D1 defect: `_classify_one` hardcodes `git_state: ""`). It is superseded by
  # the genuine end-to-end `slice-15` scenario "A feature changed after a
  # genuine classification is refused as stale", which runs the real
  # `classify_features` -> real `convert_to_atdd_pure` chain. The fixture-shaped
  # scenario was removed -- not duplicated -- so the stale-refusal contract has
  # exactly one AT, and it is the wired one.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (main(argv)).

  # --- C7a degraded resource: a non-writable feature directory -----------------

  @slice-09 @driving_port @error @contract-shape:unbounded-preservation
  Scenario: Converting a non-writable feature directory is refused and changes nothing
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    And the feature directory is not writable
    When the architect converts the feature
    Then the conversion is refused because the feature directory is not writable
    And the feature is never left half-converted
    And the pre-conversion classic artifacts are restored
