@feature-classic-spine-decommission
Feature: An architect classifies a legacy feature ready for migration
  As a solution architect retiring the classic roadmap spine
  I want a detection CLI that scans a feature directory and tells me which
    DELIVER spine it is on
  So that I can plan the conversion off classic with a deterministic worklist

  # slice-01 of classic-spine-decommission. THE walking skeleton: the thinnest
  # end-to-end vertical -- the installed `des-classify-features` CLI scans one
  # fixture feature directory and emits a one-row migration manifest. Proves the
  # toolkit's hexagonal skeleton end-to-end (driving CLI -> FeatureClassifier ->
  # FeatureScanPort) against the artifact a consumer installs.
  #
  # Genuinely end-to-end (DESIGN D6 / atdd_pure walking-skeleton mandate): a
  # real `des classify-features` subprocess against a real tmp_path feature
  # tree, manifest JSON read back from disk. No fixture-folding.
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess. Example-only, no PBT
  # (Mandate 9/11). Traditional + state-delta assertions (Mandate 8).
  #
  # Driving port: `des classify-features` (single-entry-point dispatcher form).

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @contract-shape:bounded-change
  Scenario: An architect classifies a mid-implementation classic feature
    Given the legacy feature "legacy-alpha" is a classic feature mid-implementation
    When the architect classifies the feature tree
    Then the manifest classifies "legacy-alpha" as a classic feature mid-implementation
    And the classifier did not crash

  @slice-01 @wiring_e2e @driving_port @contract-shape:unbounded-preservation
  Scenario: Classifying a feature tree leaves the developer's repository untouched
    Given the legacy feature "legacy-alpha" is a classic feature mid-implementation
    When the architect classifies the feature tree
    Then the manifest classifies "legacy-alpha" as a classic feature mid-implementation
    And the developer repository is left untouched by the classification
