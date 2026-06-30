@feature-feature-delta-section-schema @slice-01
Feature: The feature-delta section-schema is one typed value
  As an nWave maintainer
  I want the feature-delta described as ONE typed section-schema value -- a closed
    five-constructor algebra plus a section registry that routes each section to the
    waves that consume it
  So that the section knowledge lives in a single SSOT, consumed many ways without drift

  # slice-01 (walking skeleton) of feature-delta-section-schema -- ADR-FLOW-007 §S.1/§S.3.
  # DRIVING PORT (Mandate-13, Layer 3 subprocess): `des feature-delta-schema describe`
  # invoked as a real subprocess. The observable is exit code + stdout (the schema dump).
  # Active-RED (ADR-025/028): at HEAD `feature_delta_schema.main` is a scaffold raising
  # AssertionError, so the subprocess exits non-zero -- each `then` fails for the right
  # reason (the schema is not yet describable). DELIVER realizes the algebra + registry.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:pure-function
  Scenario: Maintainer describes the section-schema as one value
    When the maintainer describes the feature-delta section-schema
    Then the description succeeds end-to-end

  @slice-01 @driving_port @real-io @contract-shape:pure-function
  Scenario: The algebra is a closed five-constructor sum
    When the maintainer describes the section-schema constructors
    Then exactly the five section-type constructors are listed

  @slice-01 @driving_port @real-io @contract-shape:pure-function
  Scenario: Every registered section maps to exactly one constructor
    When the maintainer describes the feature-delta section-schema
    Then each registered section reports exactly one constructor

  @slice-01 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: Each section's consumed-by is a kebab-lowercase subset of the eight waves
    When the maintainer describes the section-schema routing
    Then every consumed-by token is a kebab-lowercase wave from the eight-wave set
