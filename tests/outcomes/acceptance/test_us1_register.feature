@us-1 @real-io @driving_adapter
Feature: outcomes registry US-1 register hardening

  Author registers outcomes via the nwave-ai CLI. The registry rejects
  duplicate ids with exit 2 and a clear stderr message, and the persisted
  YAML preserves canonical key order plus a trailing newline so the file
  remains human-readable.

  Scenario: Register a new outcome
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    When the author registers OUT-1 as a specification with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" with keywords "non-empty"
    Then the CLI register exit code is 0
    And the registry contains an entry with id OUT-1

  Scenario: Reject duplicate id
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-1 has been registered as a specification with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" with keywords "non-empty"
    When the author registers OUT-1 again with shapes X and Y and keyword k
    Then the CLI register exit code is 2
    And stderr matches /duplicate.*OUT-1/

  Scenario: Registry file is human-readable
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    And OUT-1 has been registered as a specification with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]" with keywords "non-empty"
    When the registry file is parsed back as YAML
    Then the entry keys are in canonical order id, kind, summary, feature, inputs, output, keywords, artifact, related, superseded_by
    And the registry file ends with a trailing newline
