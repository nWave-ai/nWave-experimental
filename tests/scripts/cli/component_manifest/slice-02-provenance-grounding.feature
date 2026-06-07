@feature-fix-design-component-manifest
Feature: A component manifest names real symbols and is stamped by the design wave

  A manifest is only trustworthy if the symbols it names actually exist and the
  manifest was genuinely produced by the design wave. This slice adds two
  guarantees on top of the schema: every named component symbol must be findable
  in the file the manifest cites, and every declared input domain must be
  stamped as design-wave work -- a domain hand-added by a later wave is refused.

  Read in sequence after slice-01: slice-01 told a well-formed manifest from a
  malformed one; this slice tells a manifest naming real, design-stamped symbols
  from one naming a phantom symbol or a wrong-wave stamp.

  # Driving port: the validate_component_manifest CLI (python -m invocation).
  # Layer 3 (subprocess / FS acceptance) -- example-only (Mandate 11).
  # Enforces feedback_architect_must_filesystem_ground_roadmap on the manifest
  # itself; satisfies the fix-robustness-pbt-density-gate R3 stale contract.

  Background:
    Given a feature whose design directory has been prepared

  @slice-02 @driving_port @contract-shape:pure-function
  Scenario: A manifest whose named symbols all exist is accepted
    Given the architect has written a manifest naming only real symbols
    When the architect validates the component manifest
    Then the component manifest is accepted

  @slice-02 @error @driving_port @contract-shape:pure-function
  Scenario: A manifest naming a symbol that no longer exists is refused as stale
    Given the architect has written a manifest naming a symbol absent from its file
    When the architect validates the component manifest
    Then the component manifest is refused as stale

  @slice-02 @error @driving_port @contract-shape:pure-function
  Scenario: A manifest stamped by a later wave is refused as malformed
    Given the architect has written a manifest stamped by the distill wave
    When the architect validates the component manifest
    Then the component manifest is refused as malformed
