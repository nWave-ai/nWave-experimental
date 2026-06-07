@feature-fix-design-component-manifest
Feature: An architect's component manifest is mechanically validated against a schema

  The component manifest is the DESIGN wave's structured component contract --
  the machine-readable record of what unbounded input each component accepts.
  Before any downstream gate can rely on it, the manifest must be checkable: an
  architect runs the validation tool, and a manifest that is well-formed is
  accepted while a manifest that is malformed is rejected with a clear refusal.

  This slice delivers that floor -- the schema and the validation tool. It is
  the walking skeleton: nothing else in the feature can be built or trusted
  until a manifest can be told apart from a non-manifest.

  # Driving port: the validate_component_manifest CLI (python -m invocation).
  # Layer 3 (subprocess / FS acceptance) -- example-only sad paths (Mandate 11).
  # The malformed-shape outline is @property: every malformed equivalence class
  # is rejected fail-closed -- realised as an enumerated Scenario Outline at
  # layer 3, not a Hypothesis @given (Mandate 9).

  Background:
    Given a feature whose design directory has been prepared

  @slice-01 @walking_skeleton @wiring_e2e @driving_port @contract-shape:pure-function
  Scenario: A well-formed component manifest is accepted
    Given the architect has written a well-formed component manifest
    When the architect validates the component manifest
    Then the component manifest is accepted

  @slice-01 @driving_port @contract-shape:pure-function
  Scenario: A manifest with every required and optional section present is accepted
    Given the architect has written a manifest with every section populated
    When the architect validates the component manifest
    Then the component manifest is accepted

  @slice-01 @property @error @driving_port @contract-shape:pure-function
  Scenario Outline: A malformed component manifest is refused with a clear reason
    Given the architect has written a manifest where <defect>
    When the architect validates the component manifest
    Then the component manifest is refused as malformed

    Examples:
      | defect                                              |
      | the unbounded-input-domains key is absent           |
      | the input-domains list is empty with no rationale   |
      | the manifest declares a future schema version       |
      | the manifest is not a structured mapping            |
      | the schema version is absent                        |
