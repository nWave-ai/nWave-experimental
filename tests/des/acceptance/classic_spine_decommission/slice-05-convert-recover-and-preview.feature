@feature-classic-spine-decommission
Feature: An architect converts a slice-planned feature onto the atdd_pure spine
  As a solution architect retiring the classic roadmap spine
  I want a conversion CLI that recovers a feature's slice plan, seeds its ledger,
    and previews its plan without writing anything
  So that I can convert a feature and trust a --dry-run preview is safe

  # slice-05 of classic-spine-decommission. The converter's happy path: a
  # slice-planned feature is recovered, its ledger seeded, the classic roadmap
  # archived; and `--dry-run` is proven side-effect-free.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (main(argv), --dry-run form).

  # --- Happy path: lossless deterministic conversion ---------------------------

  @slice-05 @driving_port @contract-shape:bounded-change
  Scenario: Converting a slice-planned feature recovers its plan and seeds its ledger
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    When the architect converts the feature
    Then the conversion is converted onto the atdd_pure spine
    And slice "slice-01" is reconciled as shipped
    And the feature now runs on the atdd_pure spine
    And the seeded ledger records carry sequence numbers and hashes
    And the classic roadmap artifacts are archived under the feature
    And the converted feature passes the carpaccio entry gate dry-run

  # --- C5 mode-flag: --dry-run is side-effect-free -----------------------------

  @slice-05 @driving_port @contract-shape:unbounded-preservation
  Scenario: Previewing a conversion writes nothing to the feature directory
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    When the architect previews the conversion
    Then the preview writes nothing to the feature directory
