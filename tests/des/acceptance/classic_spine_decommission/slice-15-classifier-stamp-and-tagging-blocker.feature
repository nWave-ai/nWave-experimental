@feature-classic-spine-decommission
Feature: An architect's conversion trusts a real classifier stamp and surfaces a tagging blocker
  As a solution architect retiring the classic roadmap spine
  I want the converter's staleness guard fed by the real classifier's own
    git_state stamp, and a single-feature --dry-run to surface an untagged
    .feature scenario as a tagging blocker
  So that a feature changed after a genuine classification is refused
    end-to-end, and a feature that DISTILL has not finished tagging is flagged
    before any side effect is applied

  # slice-15 of classic-spine-decommission. The feature-end-review gap slice
  # (DESIGN [REF] Feature-End-Review Amendment): two "exists != wired" defects.
  #
  # D1 -- the production classifier `classify_features._classify_one` must emit
  # a non-empty `git_state` (the feature dir's git tree-object SHA at HEAD), so
  # the converter's M7 `_feature_dir_is_stale` guard is reachable end-to-end.
  # The first scenario runs the REAL `classify_features` -> REAL
  # `convert_to_atdd_pure` chain -- NO hand-written manifest. It supersedes the
  # fixture-shaped slice-09 stale-refusal scenario (consolidated: that scenario
  # was removed, this one carries the genuine end-to-end coverage).
  #
  # D2-Step-3 -- a single-feature `--dry-run` on a feature whose `.feature` file
  # carries an untagged scenario must surface `blocker: blocked-needs-distill-
  # tagging` in the ConversionPlan and apply ZERO side effect (exit 0, clean
  # outcome -- symmetric with a refusal). The current converter ATs never drive
  # a non-None `blocker`.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving ports: `des.cli.classify_features` + `des.cli.convert_to_atdd_pure`.

  # --- D1: the real classifier's git_state stamp drives the staleness guard ----

  @slice-15 @driving_port @error @contract-shape:unbounded-preservation
  Scenario: A feature changed after a genuine classification is refused as stale
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    And the architect has classified the feature with the real classifier
    And the feature directory changes after the real classification
    When the architect converts the feature
    Then the conversion is refused as a stale manifest row
    And the feature is never left half-converted
    And the classic roadmap artifacts are not archived under the feature

  # --- D2-Step-3: a single-feature --dry-run surfaces the tagging blocker -------

  @slice-15 @driving_port @error @contract-shape:unbounded-preservation
  Scenario: Previewing a feature with untagged scenarios surfaces a tagging blocker
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    And the feature's acceptance scenarios carry no slice tags
    When the architect previews the conversion
    Then the preview reports the conversion would be blocked pending DISTILL tagging
    And the preview writes nothing to the feature directory
