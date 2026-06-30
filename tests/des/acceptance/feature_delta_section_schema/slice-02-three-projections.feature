@feature-feature-delta-section-schema @slice-02
Feature: The schema value drives three total pure projections
  As an nWave maintainer
  I want the one section-schema value to drive gate-verify, wave-injection and
    output-contract -- three total pure projections derived from the same registry
  So that a section is authored once and consumed three ways with zero drift (OUT is IN)

  # slice-02 of feature-delta-section-schema -- ADR-FLOW-007 §S.4.
  # DRIVING PORT (Mandate-13, Layer 3 subprocess): `des feature-delta-schema
  # {verify,inject,contract}` invoked as real subprocesses. P1 (gate-verify) DELEGATES
  # per-Table validation to the shipped `validate_slice_plan_content` /
  # `validate_reuse_analysis_content` (REUSE, no re-implementation). The verify ATs
  # arrange a real feature-delta `.md` in a hermetic tmp_path.
  # Active-RED: at HEAD the scaffold raises, so verify/inject/contract exit non-zero.

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: gate-verify passes a well-formed feature-delta
    Given a well-formed feature-delta document
    When the schema gate verifies the document
    Then the verdict is pass

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: gate-verify fails fail-closed naming the offending section
    Given a feature-delta whose slice-plan table header is reordered
    When the schema gate verifies the document
    Then the verdict is fail naming the slice-plan section

  @slice-02 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: gate-verify is indeterminate on an unreadable document
    Given a feature-delta document that cannot be decoded
    When the schema gate verifies the document
    Then the verdict is indeterminate and never a silent pass

  @slice-02 @driving_port @real-io @property @contract-shape:pure-function
  Scenario: wave-injection projects exactly the sections a wave consumes
    When the schema injects sections for the distill wave
    Then the projected rows are exactly the sections whose consumed-by includes distill

  @slice-02 @driving_port @real-io @contract-shape:pure-function
  Scenario: output-contract returns the write spec for a section
    When the maintainer requests the write contract for the architecture-and-contract-tests section
    Then the write spec carries the section's heading literal
