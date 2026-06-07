@walking_skeleton @real-io @driving_adapter
Feature: outcomes registry walking skeleton

  Author registers an outcome via the nwave-ai CLI and detects a Tier-1
  shape collision via a second CLI subcommand. Real subprocess + real
  YAML filesystem I/O — no mocks at the acceptance boundary.

  Scenario: Author registers an outcome and detects a Tier-1 collision
    Given a clean docs/product/outcomes/registry.yaml under tmp_path
    When the author registers OUT-A as a specification with input shape "FeatureDeltaModel" and output shape "tuple[Violation, ...]"
    Then the registry contains OUT-A
    When the author runs check with the same shapes
    Then the CLI exits with code 1
    And stdout reports a collision with OUT-A
