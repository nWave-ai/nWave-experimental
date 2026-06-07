@us-3 @real-io @driving_adapter
Feature: outcomes registry US-3 check-delta (aggregate scan over feature-delta.md)

  Author runs `nwave-ai outcomes check-delta <path>` to scan a freshly-emitted
  feature-delta.md for OUT-id references, run a per-id collision check (with
  self-exclusion so an outcome doesn't collide with itself), and emit an
  aggregate report. Exit 1 if any collision found, 0 otherwise.

  Scenario: Aggregate scan over feature-delta
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-1 has been registered with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" and keywords "cherry-pick,row-count"
    And OUT-COLLIDER has been registered with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" and keywords "cherry-pick,row-count"
    And OUT-2 has been registered with input shape "int" and output shape "bool" and keywords "totally,different"
    And OUT-3 has been registered with input shape "str" and output shape "list[str]" and keywords "alpha,beta"
    And a feature-delta.md exists referencing OUT-1, OUT-2, OUT-3
    When the author runs check-delta on the feature-delta.md
    Then the CLI check-delta exit code is 1
    And stdout contains "3 outcomes checked"
    And stdout contains "1 collision found"
