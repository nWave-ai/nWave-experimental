@us-2 @real-io @driving_adapter
Feature: outcomes registry US-2 check (Tier-1 + Tier-2 verdict pipeline)

  Author runs `nwave-ai outcomes check` to detect collisions before locking
  a decision. Two-tier detector: Tier-1 (exact normalized shape) +
  Tier-2 (keyword Jaccard >= 0.4). Verdict matrix from DESIGN spec:
  Tier-1 + Tier-2 -> collision; Tier-1 alone or Tier-2 alone -> ambiguous;
  neither -> clean. Real subprocess + real YAML filesystem I/O.

  Scenario: Tier-1 catch on identical shape
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-E3 has been registered with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" and keywords "cherry-pick,row-count"
    When the author runs check with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" and keywords "cherry-pick,row-count"
    Then the CLI check exit code is 1
    And stdout contains "OUT-E3"
    And stdout contains "COLLISION:"
    And stdout contains "Tier-1 + Tier-2"

  Scenario: Tier-1 + Tier-2 disambiguates same-shape different-intent
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-E1 has been registered with input shape "(text: str, file_path: str)" and output shape "tuple[Violation, ...]" and keywords "section,heading,wave,format"
    When the author runs check with input shape "(text: str, file_path: str)" and output shape "tuple[Violation, ...]" and keywords "column,ddd,table,header"
    Then the CLI check exit code is 1
    And stdout contains "AMBIGUOUS"
    And stdout contains "OUT-E1"

  Scenario: No collision on unique shape
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-E1 has been registered with input shape "(text: str, file_path: str)" and output shape "tuple[Violation, ...]" and keywords "section,heading"
    When the author runs check with input shape "int" and output shape "bool" and keywords "totally,different"
    Then the CLI check exit code is 0
    And stdout contains "NO COLLISIONS"

  Scenario: format_suggestion drift detection
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-FORMAT has been registered with input shape "(why: str, how: str, action: str)" and output shape "str" and keywords "format,suggestion,render"
    When the author runs check with input shape "(str, str, str)" and output shape "str" and keywords "format,suggestion,message"
    Then the CLI check exit code is 1
    And stdout contains "OUT-FORMAT"
    And stdout contains "COLLISION"
