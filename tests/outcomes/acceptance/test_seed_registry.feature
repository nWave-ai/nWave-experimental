@step-03-02 @real-io @driving_adapter
Feature: Seeded production outcomes registry exposes the 6 spike outcomes

  Step 03-02 — migrates the 6 hand-curated spike outcomes
  (OUT-E1..E5 + OUT-FORMAT) from nwave_ai/outcomes/spike/registry.yaml
  to docs/product/outcomes/registry.yaml as the production seed, and
  removes the spike directory.

  This scenario locks the END-TO-END strategy validation: the production
  registry IS populated with real outcomes, and the production CLI
  resolves expected verdicts against it.

  Scenario: Seeded registry resolves expected collision verdict for OUT-E3
    Given the production registry at docs/product/outcomes/registry.yaml
    And the registry contains all 6 seeded outcomes
    When the author runs check against the production registry with input shape "FeatureDeltaModel" and output shape "tuple[ValidationViolation, ...]" and keywords "non-empty,required,cell"
    Then the CLI check exit code is 1
    And stdout contains "OUT-E3"
    And stdout contains "COLLISION"
